import sys
from pathlib import Path
import unittest
from unittest.mock import patch

import numpy as np


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from rtmpose import (
    DeviceFallbackInferencer,
    HALPE26_LANDMARKS,
    HALPE26_SKELETON,
    _bbox,
    create_output_video_writer,
    infer_frame,
    inferencer_init_kwargs,
    instance_keypoints,
    landmarks_for_model,
    normalize_video_writer_fps,
    pose_layout_for_model,
    resolve_device,
    select_instances,
    skeleton_for_model,
)


class RTMPoseHelpersTest(unittest.TestCase):
    def test_high_fractional_fps_is_safe_for_mpeg4_timebase(self):
        self.assertEqual(normalize_video_writer_fps(239.483), 239.48)

    def test_invalid_fps_uses_30_fps(self):
        for value in (0, -1, float("nan"), float("inf"), None, "invalid"):
            with self.subTest(value=value):
                self.assertEqual(normalize_video_writer_fps(value), 30.0)

    @patch("rtmpose.cv2.VideoWriter_fourcc", return_value=1234)
    @patch("rtmpose.cv2.VideoWriter")
    def test_video_writer_receives_normalized_fps(self, writer_class, fourcc):
        writer = writer_class.return_value
        writer.isOpened.return_value = True

        result, output_fps = create_output_video_writer(
            "output.mp4", 239.483, (1920, 1080)
        )

        self.assertIs(result, writer)
        self.assertEqual(output_fps, 239.48)
        fourcc.assert_called_once_with(*"mp4v")
        writer_class.assert_called_once_with(
            "output.mp4", 1234, 239.48, (1920, 1080)
        )

    def test_auto_detector_uses_model_default(self):
        parameters = {"model": "body26", "detector": "auto"}
        self.assertEqual(
            inferencer_init_kwargs(parameters, "mps"),
            {"pose2d": "body26", "device": "mps"},
        )

    def test_custom_detector_is_forwarded(self):
        parameters = {"model": "body26", "detector": "custom_detector.py"}
        self.assertEqual(
            inferencer_init_kwargs(parameters, "cpu"),
            {
                "pose2d": "body26",
                "det_model": "custom_detector.py",
                "device": "cpu",
            },
        )

    def test_mps_moves_only_detector_model_to_cpu(self):
        moved_to = []

        class DetectorModel:
            def to(self, device):
                moved_to.append(device)

        class Detector:
            model = DetectorModel()

        class PoseInferencer:
            detector = Detector()

        class Backend:
            inferencer = PoseInferencer()

        runtime = DeviceFallbackInferencer(
            lambda **kwargs: Backend(),
            {"pose2d": "body26", "device": "mps"},
        )

        self.assertEqual(moved_to, ["cpu"])
        self.assertEqual(runtime.used_device, "mps")
        self.assertEqual(runtime.detector_device, "cpu")

    def test_body26_alias_selects_halpe26_layout(self):
        self.assertEqual(pose_layout_for_model("body26"), "halpe26")
        self.assertEqual(landmarks_for_model("body26"), HALPE26_LANDMARKS)
        self.assertEqual(skeleton_for_model("body26"), HALPE26_SKELETON)
        self.assertEqual(len(landmarks_for_model("body26")), 26)

    def test_halpe26_config_name_selects_halpe26_layout(self):
        model = "rtmpose-m_8xb512-700e_body8-halpe26-256x192"
        self.assertEqual(pose_layout_for_model(model), "halpe26")

    def test_human_alias_keeps_coco17_layout(self):
        self.assertEqual(pose_layout_for_model("human"), "coco17")
        self.assertEqual(len(landmarks_for_model("human")), 17)

    def test_body26_contains_toe_and_heel_keypoints(self):
        landmarks = dict(landmarks_for_model("body26"))
        self.assertIn("つま先", landmarks[20])
        self.assertIn("つま先", landmarks[23])
        self.assertEqual(landmarks[24], "左かかと")
        self.assertEqual(landmarks[25], "右かかと")
        self.assertTrue(all(max(link) < 26 for link in HALPE26_SKELETON))

    def test_select_instances_uses_score_limit_then_left_to_right(self):
        result = {
            "predictions": [[
                {"bbox": [200, 0, 300, 100], "bbox_score": 0.9},
                {"bbox": [10, 0, 100, 100], "bbox_score": 0.8},
                {"bbox": [0, 0, 50, 100], "bbox_score": 0.1},
            ]]
        }

        selected = select_instances(result, 2)

        self.assertEqual([_bbox(item)[0] for item in selected], [10.0, 200.0])

    def test_instance_keypoints_accepts_batched_lists(self):
        points, scores = instance_keypoints(
            {
                "keypoints": [[[1.0, 2.0], [3.0, 4.0]]],
                "keypoint_scores": [[0.8, 0.9]],
            }
        )

        self.assertEqual(points, [[1.0, 2.0], [3.0, 4.0]])
        self.assertEqual(scores, [0.8, 0.9])

    def test_instance_keypoints_accepts_numpy_arrays(self):
        points, scores = instance_keypoints(
            {
                "keypoints": np.array([[[1.0, 2.0], [3.0, 4.0]]]),
                "keypoint_scores": np.array([[0.8, 0.9]]),
            }
        )

        self.assertEqual(points, [[1.0, 2.0], [3.0, 4.0]])
        self.assertEqual(scores, [0.8, 0.9])

    def test_infer_frame_passes_detection_thresholds(self):
        calls = []

        def fake_inferencer(frame, **kwargs):
            calls.append((frame, kwargs))
            yield {
                "predictions": [
                    [{"bbox": [1, 2, 3, 4], "bbox_score": 0.9}]
                ]
            }

        parameters = {
            "bbox_threshold": 0.4,
            "nms_threshold": 0.5,
            "max_instances": 1,
        }
        frame = object()

        instances = infer_frame(fake_inferencer, frame, parameters)

        self.assertEqual(len(instances), 1)
        self.assertIs(calls[0][0], frame)
        self.assertEqual(
            calls[0][1],
            {"return_vis": False, "bbox_thr": 0.4, "nms_thr": 0.5},
        )

    @patch("rtmpose.cuda_available", return_value=True)
    def test_auto_device_uses_selected_cuda_index(self, _cuda_available):
        parameters = {"device": "AUTO", "cuda_index": 2}
        self.assertEqual(resolve_device(parameters), "cuda:2")

    @patch("rtmpose.cuda_available", return_value=False)
    def test_cuda_request_falls_back_to_cpu(self, _cuda_available):
        parameters = {"device": "CUDA", "cuda_index": 0}
        self.assertEqual(resolve_device(parameters), "cpu")

    @patch("rtmpose.mps_available", return_value=True)
    @patch("rtmpose.cuda_available", return_value=False)
    def test_auto_device_uses_mps_on_apple_gpu(
        self, _cuda_available, _mps_available
    ):
        parameters = {"device": "AUTO", "cuda_index": 0}
        self.assertEqual(resolve_device(parameters), "mps")

    @patch("rtmpose.mps_available", return_value=False)
    def test_mps_request_falls_back_to_cpu(self, _mps_available):
        parameters = {"device": "MPS", "cuda_index": 0}
        self.assertEqual(resolve_device(parameters), "cpu")

    def test_runtime_failure_rebuilds_inferencer_on_cpu(self):
        built_devices = []

        class FakeBackend:
            def __init__(self, device):
                self.device = device

            def __call__(self, frame, **kwargs):
                if self.device == "mps":
                    raise NotImplementedError("unsupported MPS operation")
                yield {"predictions": [[]]}

        def builder(**kwargs):
            built_devices.append(kwargs["device"])
            return FakeBackend(kwargs["device"])

        runtime = DeviceFallbackInferencer(
            builder,
            {"pose2d": "human", "det_model": "human", "device": "mps"},
        )

        result = next(runtime(object()))

        self.assertEqual(result, {"predictions": [[]]})
        self.assertEqual(runtime.used_device, "cpu")
        self.assertEqual(built_devices, ["mps", "cpu"])


if __name__ == "__main__":
    unittest.main()
