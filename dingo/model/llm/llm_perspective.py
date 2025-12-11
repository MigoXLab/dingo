import time

from dingo.config.input_args import EvaluatorLLMArgs
from dingo.io import Data
from dingo.io.output.eval_detail import EvalDetail, QualityLabel
from dingo.model import Model
from dingo.model.llm.base import BaseLLM
from dingo.utils import log


@Model.llm_register("LLMPerspective")
class LLMPerspective(BaseLLM):
    dynamic_config = EvaluatorLLMArgs(
        api_url="https://commentanalyzer.googleapis.com/$discovery/rest?version=v1alpha1"
    )

    @classmethod
    def create_client(cls):
        try:
            from googleapiclient import discovery
        except ImportError:
            log.warning(
                "=========== perspective register fail. Please check whether install googleapiclient. ==========="
            )

        if cls.client is None:
            if not cls.dynamic_config.key:
                raise ValueError("key cannot be empty in llm config.")
            elif not cls.dynamic_config.api_url:
                raise ValueError("api_url cannot be empty in llm config.")
            else:
                cls.client = discovery.build(
                    "commentanalyzer",
                    "v1alpha1",
                    developerKey=cls.dynamic_config.key,
                    discoveryServiceUrl=cls.dynamic_config.api_url,
                    static_discovery=False,
                )

    @classmethod
    def eval(cls, input_data: Data) -> EvalDetail:
        cls.create_client()
        analyze_request = {
            "comment": {"text": input_data.content},
            "requestedAttributes": {
                "TOXICITY": {},
                "SEVERE_TOXICITY": {},
                "IDENTITY_ATTACK": {},
                "INSULT": {},
                "PROFANITY": {},
                "THREAT": {},
                # 'SEXUALLY_EXPLICIT': {},
                # 'FLIRTATION': {},
            },
        }

        attempts = 0
        except_msg = ""
        while attempts < 3:
            try:
                response = cls.client.comments().analyze(body=analyze_request).execute()

                is_good = True
                error_list = []
                for e in response["attributeScores"]:
                    value = response["attributeScores"][e]["summaryScore"]["value"]
                    if value > 0.6:
                        is_good = False
                        error_list.append(e)

                if is_good:
                    res = EvalDetail(metric=cls.__name__)
                    res.status = False
                    res.label = [f"{QualityLabel.QUALITY_GOOD}.PERSPECTIVE"]
                    res.reason = []
                    return res
                else:
                    res = EvalDetail(metric=cls.__name__)
                    res.status = True
                    res.label = ["QUALITY_BAD.PERSPECTIVE"]
                    res.reason = error_list
                    return res
            except Exception as e:
                attempts += 1
                time.sleep(1)
                except_msg = str(e)

        res = EvalDetail(metric=cls.__name__)
        res.status = True
        res.label = ["QUALITY_BAD.API_LOSS"]
        res.reason = [except_msg]
        return res
