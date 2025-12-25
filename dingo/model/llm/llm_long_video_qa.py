from dingo.io.output.eval_detail import EvalDetail
from dingo.model import Model
from dingo.model.llm.base_openai import BaseOpenAI
from dingo.utils import log


@Model.llm_register("LLMLongVideoQa")
class LLMLongVideoQa(BaseOpenAI):
    # Metadata for documentation generation
    _metric_info = {
        "category": "Text Generation",
        "metric_name": "PromptLongVideoQa",
        "paper_title": "VRBench: A Benchmark for Multi-Step Reasoning in Long Narrative Videos",
        "paper_url": "https://arxiv.org/abs/2506.108572",
        "paper_authors": "Jiashuo Yu et al., 2025",
        "evaluation_results": "",
        "description": "Generate video-related question-answer pairs based on the summarized information of the input long video.",
    }

    prompt = """
            ### Background
            You will be given a video summary text that chronologically records the content of the video. Your task is to infer the complete story of events in the video based on the summary content and generate 6 multi-step reasoning Q&A pairs that satisfy the <Output Format>.

            ### Objective
            Multi-step reasoning questions: The questions should require logical reasoning to answer, rather than being based on direct observation or perception. The design of the questions should promote a deep understanding of the entire plot, not just simple recognition of single scenes or objects.
            Multi-step reasoning process: Beyond basic event overviews, the answers should be derived through multiple steps of logical thinking and information integration. This means drawing conclusions from given information rather than stating obvious facts.
            Combining multiple information sources: While questions and answers can be resolved through visual content alone or by combining video and subtitles, they should not rely solely on subtitle information or everyday common sense. This requires comprehensive consideration of information from different channels to form a complete understanding.
            Generation result: You must generate exactly 6 Q&A pairs.

            ### Question Categories and Multi-step Reasoning Examples
            ## 1. Event Prediction
            Definition: Predict subsequent plot developments based on events that have already occurred in the video.
            # Example
            Question: How will the miscarriage caused by the woman in pink being accidentally hurt while trying to break up a fight affect the subsequent plot?
            Answer: It may lead to a rift between the man in the blue vest and the man in green.
            Reasoning process:
            1. The woman trying to break up the fight was accidentally hurt, seen lying in bed holding her stomach, with doctors diagnosing a miscarriage
            2. The woman has a close relationship with the man in the blue vest
            3. The man in the blue vest will become angrier with the man in green
            4. The man in the blue vest and the man in green will have a falling out

            ## 2. Hypothetical Reasoning
            Definition: Present a hypothetical premise and infer corresponding developments.
            # Example
            Question: If the characters continue participating in the desert competition, what challenges might they face?
            Answer: They might face physical discomfort or even life-threatening challenges.
            Reasoning process:
            1. The characters are in an arid desert environment with harsh conditions
            2. The harsh environment has already caused physical discomfort in some participants
            3. Continued competition would likely lead to more severe physical discomfort or life-threatening situations

            ## 3. Event Attribution
            Definition: Determine the cause or purpose of an event in the video.
            # Example
            Question: Why does the streamer describe Kaveh as a good person?
            Answer: Because Kaveh donated all the property he won from the competition to those in need.
            Reasoning process:
            1. Kaveh won Sachin's property through the competition
            2. Kaveh donated all the won property to those in need
            3. Therefore the streamer describes Kaveh as a good person

            ## 4. Implicit Inference
            Definition: Analyze implicit information not explicitly shown, such as character personalities, emotions, relationships, event atmosphere, or situations.
            # Example
            Question: Why does the streamer share the story about his daughter Rin with viewers?
            Answer: Because the character he's using has a snake around its neck, reminding him of his daughter Rin's story about not being afraid of snakes, which he finds interesting enough to share.
            Reasoning process:
            1. The streamer is introducing his character Baizhu, who has a snake around the neck
            2. He mentions his daughter Rin wanted to keep a snake and wasn't afraid even at close range
            3. He likely finds this story interesting
            4. Therefore he shares it with viewers

            ## 5. Logical Connection
            Definition: Analyze the correlation between two elements in the video and explain their logical relationship, which can also be linked through events serving as intermediate connecting elements.
            # Example
            Question: What is the relationship between the man in the black jacket and his surroundings?
            Answer: He is very familiar with the environment.
            Reasoning process (adjust steps as needed):
            1. The man in black jacket appears multiple times smiling and relaxed
            2. People tend to relax in familiar environments
            3. Therefore he must be familiar with this environment

            ## 6. Event Summary
            Definition: Pose a summary question about the video content and provide an answer.
            # Example
            Question: What is the theme of this livestream?
            Answer: The streamer completing a Genshin Impact quest involving multiple characters competing, with Kaveh ultimately winning.

            ## 7. Multi-element Inference
            Definition: Infer event transformations after considering multiple conditions, with questions containing computational or counting components (numbers, dates, time points) derived from different elements.
            # Example
            Question: How many characters did the streamer use in the game?
            Answer: The streamer used 4 characters.
            Reasoning process:
            1. Used Nahida
            2. Used Zhongli
            3. Used Yae Miko
            4. Used Baizhu
            5. Total of 4 characters used

            ### Output Format
            Question1: [question]
            Answer1: [answer]
            Reasoning1: [detailed multi-step reasoning]
            Type1: [reasoning type]

            ### Workflow
            1. Carefully read the provided subtitles and summary.
            2. Generate exactly 6 multi-step reasoning Q&A pairs, ensuring each type is represented with even distribution.
            3. Format answers according to the specified <Output Format>, ensuring each step is supported by logical reasoning derived from the text.

            ### Provided Text
            """

    @classmethod
    def process_response(cls, response: str) -> EvalDetail:
        log.info(response)
        result = EvalDetail(metric=cls.__name__)
        result.status = False
        result.label = ["text.qa_pairs"]
        result.reason = [response]

        return result
