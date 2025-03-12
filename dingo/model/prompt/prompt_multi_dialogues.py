from dingo.model.model import Model
from dingo.model.prompt.base import BasePrompt


@Model.prompt_register("QUALITY_BAD_DIALOGUES", [])
class PromptMultiTurnDialogues(BasePrompt):
    content = """
    Please act as an impartial quality assessor and evaluate the AI assistant's response in the following conversation. Focus on the last response from the assistant and score it on a scale of 1 to 10 based on these criteria:

    1. Accuracy and Completeness (0-3 points)
       - Information accuracy and factual correctness
       - Comprehensive coverage of all aspects of the question
       - Appropriate level of detail

    2. Logical Reasoning (0-3 points)
       - Clear and structured thought process
       - Valid arguments and conclusions
       - Proper use of examples or evidence when needed

    3. Context Coherence (0-2 points)
       - Consistency with conversation history
       - Appropriate reference to previous exchanges
       - Maintains topic relevance

    4. Expression Quality (0-2 points)
       - Clear and concise language
       - Well-organized presentation
       - Professional and appropriate tone

    Scoring Guidelines:
    1-3 points: Major issues in accuracy or reasoning
    4-6 points: Satisfactory but with notable flaws
    7-9 points: Strong performance with minor imperfections
    10 points: Exceptional response meeting all criteria

    Conversation History:
    %s

    Assistant's Response to Evaluate:
    %s

    Please provide a detailed evaluation for each criterion, return the results in JSON format:
    {"score": 1-10, "reason": "your detailed evaluation"}. Do not output any additional content.
    """
