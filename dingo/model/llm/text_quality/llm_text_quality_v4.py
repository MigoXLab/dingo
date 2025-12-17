from dingo.model import Model
from dingo.model.llm.text_quality.base_text_quality import BaseTextQuality


@Model.llm_register("LLMTextQualityV4")
class LLMTextQualityV4(BaseTextQuality):
    # Metadata for documentation generation
    _metric_info = {
        "category": "Pretrain Text Quality Assessment Metrics",
        "metric_name": "LLMTextQualityV4",
        "description": "Enhanced text quality evaluation covering completeness (formulas, tables, code), effectiveness (garbled text, spacing), similarity (duplicates), and security (politics, prohibited content)",
        "paper_title": "WanJuanSiLu: A High-Quality Open-Source Webtext Dataset for Low-Resource Languages",
        "paper_url": "https://arxiv.org/abs/2501.14506",
        "paper_authors": "Yu et al., 2025",
        "evaluation_results": "docs/eval/prompt/redpajama_data_evaluated_by_prompt.md"
    }
    prompt = """
    # Role
    You are an expert in language model evaluation.

    # Background
    The dataset is a compilation from diverse sources, encompassing social media, news articles, academic publications, and online discussions.

    # Goals
    Your core task is to evaluate the fitness of this dataset for training a large language model. Text that exhibits any of the listed negative attributes will be flagged as low-quality data.

    # Criteria
    1. **Completeness**
        - **Error_Formula**: A formula enclosed in a pair of one $character is an intra line formula, while a formula enclosed in a pair of double $characters is an inter line formula. The text formula contains the following errors:
            - **Grammar Error**: There is a syntax error in the formula within the $ character.
            - **Interline Error**: Double $$ is used excessively for formulas that should be inline (e.g., $\\mathbf{x}$, $\\mathbf{y}$), resulting in a large number of unnecessary line breaks, severely disrupting the structure of the text, and affecting its readability and continuity.
        - **ERROR_Table**: Tables exist in Markdown files in either Markdown format or HTML format.
            - **Simple_Table_Errors**: Simple tables exist in the document in markdown format, specifically referring to tables without row/column spans or nested tables; error reasons include format and content issues.
            - **Complex_Table_Errors**: Complex tables exist in the document in HTML format, specifically referring to tables with row/column spans or nested tables; error reasons include format and content issues.
        - **Error_Code**: A Code enclosed in a pair of one `characters is an intra line code, while a code enclosed in a pair of three `characters is an inter line code. There are ordered numbers before code or the code contains syntax Error, format Error.

    2. **Effectiveness**
        - **Error_Garbled_Characters**: High presence of garbled or anti-crawler characters.
        - **Error_Words_Stuck**: Words clustered together without spaces (excluding hyphenated words; treat \n as spaces).
        - **Error_Lack_Punctuation**: Words piled up without forming coherent sentences.

    3. **Similarity**
       - **Error_Duplicate**: Consecutive repetitions or excessive character occurrences.

    4. **Security**
       - **Error_Politics**: Harmful political statements affecting socialist systems, China's interests, unity, stability, promoting terrorism/extremism, or ethnic hatred/discrimination.
       - **Error_Prohibition**: Content involving violence, pornography, gambling, or drugs.

    # Workflow
    1. **Read and Evaluate**: Analyze the text based on the outlined negative criteria.
    2. **Assign Type**:
       - If no negative criteria are met, assign 'Good'.
       - Otherwise, assign one of ['Completeness', 'Effectiveness', 'Similarity', 'Security'].
    3. **Assign Name**:
       - 'Good' text gets 'None'.
       - 'Completeness' text gets one of ['Error_Formula', 'ERROR_Table', 'Error_Code'].
       - 'Effectiveness' text gets one of ['Error_Garbled_Characters', 'Error_Words_Stuck', 'Error_Lack_Punctuation'].
       - 'Similarity' text gets 'Error_Duplicate'.
       - 'Security' text gets one of ['Error_Politics', 'Error_Prohibition'].
    4. **Assign Score**: 'Good' = 1, others = 0.
    5. **Provide Reason**: Clearly state the basis for evaluation.
    6. **Return in JSON**: {"score": 0/1, "type": "", "name": "", "reason": ""}.

    # Warning
    Only output JSON format data, without any extraneous content.

    # Input content

    """
    # process_response method is now inherited from BaseTextQuality
