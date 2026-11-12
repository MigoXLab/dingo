"""Loop parameter serialization must remain reproducible and secret-safe."""

from dingo.config import InputArgs


def test_loop_settings_survive_safe_input_args_serialization():
    settings = {
        "threshold": 0.87,
        "min_repeats": 4,
        "result_ngram_size": 3,
        "result_match_mode": "exact",
    }
    args = InputArgs(evaluator=[{"evals": [{
        "name": "RuleAgentTraceLoopDetection",
        "config": {**settings, "secret_token": "placeholder-secret"},
    }]}])
    saved = args.to_dict()
    config = saved["evaluator"][0]["evals"][0]["config"]
    assert {key: config[key] for key in settings} == settings
    assert "secret_token" not in config
    restored = InputArgs(**saved).evaluator[0].evals[0].config
    assert {key: getattr(restored, key) for key in settings} == settings
