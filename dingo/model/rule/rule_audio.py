from pathlib import Path

import numpy as np

from dingo.config.input_args import EvaluatorRuleArgs
from dingo.io import Data
from dingo.io.output.eval_detail import EvalDetail, QualityLabel
from dingo.model.model import Model
from dingo.model.rule.base import BaseRule


@Model.rule_register(
    "QUALITY_BAD_EFFECTIVENESS",
    [
        "multi_lan_ar",
        "multi_lan_ko",
        "multi_lan_ru",
        "multi_lan_th",
        "multi_lan_vi",
        "multi_lan_cs",
        "multi_lan_hu",
        "multi_lan_sr",
    ],
)
class RuleAudioDuration(BaseRule):
    """check whether the audio duration meets the standard"""

    # Metadata for documentation generation
    _metric_info = {
        "category": "Audio Quality Metrics",
        "quality_dimension": "Audio_EFFECTIVENESS",
        "metric_name": "RuleAudioDuration",
        "description": "Check whether the audio duration meets the standard",
        "evaluation_results": ""
    }

    dynamic_config = EvaluatorRuleArgs()

    @classmethod
    def eval(cls, input_data: Data) -> EvalDetail:
        import librosa
        from scipy.signal import welch

        res = EvalDetail(metric=cls.__name__)

        y, sr = librosa.load(input_data.content, sr=16000)
        f_signal, Pxx_signal = welch(y, fs=sr)
        noise_threshold = np.percentile(Pxx_signal, 50)
        Pxx_noise = np.where(Pxx_signal <= noise_threshold, Pxx_signal, 0)
        signal_power = np.sum(Pxx_signal)
        noise_power = np.sum(Pxx_noise)

        if noise_power == 0:
            res.status = True
            res.label = [f"{cls.metric_type}.{cls.__name__}"]
            res.reason = ["The audio power is zero. Cannot calculate SNR."]
            return res

        snr_dB = round(10 * np.log10(signal_power / noise_power), 2)

        if snr_dB < 8:
            res.status = True
            res.label = [f"{cls.metric_type}.{cls.__name__}"]
            res.reason = ["The audio signal-to-noise ratio is too low."]
        else:
            res.label = [QualityLabel.QUALITY_GOOD]
        return res


@Model.rule_register(
    "QUALITY_BAD_EFFECTIVENESS",
    [
        "multi_lan_ar",
        "multi_lan_ko",
        "multi_lan_ru",
        "multi_lan_th",
        "multi_lan_vi",
        "multi_lan_cs",
        "multi_lan_hu",
        "multi_lan_sr",
    ],
)
class RuleAudioSnrQuality(BaseRule):
    """check whether the audio signal-to-noise ratio meets the standard"""

    # Metadata for documentation generation
    _metric_info = {
        "category": "Audio Quality Metrics",
        "quality_dimension": "Audio_EFFECTIVENESS",
        "metric_name": "RuleAudioSnrQuality",
        "description": "Check whether the audio signal-to-noise ratio meets the standard",
        "evaluation_results": ""
    }

    dynamic_config = EvaluatorRuleArgs()

    @classmethod
    def eval(cls, input_data: Data) -> EvalDetail:
        import wave

        res = EvalDetail(metric=cls.__name__)
        if not input_data.content:
            return res
        if isinstance(input_data.content, str):
            with wave.open(str(Path(input_data.content)), 'r') as w:
                frame_count = w.getnframes()
                sample_rate = w.getframerate()
                duration = frame_count / sample_rate

        if duration > 10:
            res.status = True
            res.label = [f"{cls.metric_type}.{cls.__name__}"]
            res.reason = ["The audio duration is too long."]
        else:
            res.label = [QualityLabel.QUALITY_GOOD]
        return res


if __name__ == "__main__":
    data = Data(data_id="1", content=r"../test/data/audio/test.wav")
    res = RuleAudioDuration().eval(data)
    print(res)
