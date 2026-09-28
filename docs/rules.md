The specific rules for each quality metric are as follows:

| Function Name                | Type              | Description                                                                           | Reference                                                                                                                                                                                                           |
|------------------------------|-------------------|---------------------------------------------------------------------------------------|---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| RuleAbnormalChar | EFFECTIVENESS | Check whether content contains abnormal characters. | |
| RuleAbnormalHtml | EFFECTIVENESS | Check whether content contains abnormal HTML. | |
| RuleAbnormalNumber | FLUENCY | Check PDF content for abnormal page or index numbers. | |
| RuleAgentTraceLatencyAnomaly | AGENT_TRACE_QUALITY | Detect abnormally slow agent steps using statistical outlier analysis. | |
| RuleAgentTraceLoopDetection | AGENT_TRACE_QUALITY | Detect repetitive tool-call patterns that indicate loops. | |
| RuleAgentTraceTokenBudget | AGENT_TRACE_QUALITY | Check whether agent token usage exceeds the configured budget. | |
| RuleAlphaWords | EFFECTIVENESS     | check whether the ratio of words that contain at least one alphabetic character > 0.6 | [Redpajama](https://www.together.ai/blog/redpajama-data-v2) [MAP-en](https://arxiv.org/abs/2405.19327) [Gopher](https://arxiv.org/abs/2112.11446) [Dolma](https://arxiv.org/abs/2402.00159)                         |
| RuleAudioDataFormat | EFFECTIVENESS | Check whether audio data has the expected format. | |
| RuleAudioDuration | EFFECTIVENESS | Check whether audio duration meets the configured standard. | |
| RuleAudioSnrQuality | EFFECTIVENESS | Check whether the audio signal-to-noise ratio meets the configured standard. | |
| RuleAuthorFieldValidation | EFFECTIVENESS | Validate scientific metadata author fields. | |
| RuleCapitalWords | UNDERSTANDABILITY | check whether capital words ratio > 0.2                                               | [Redpajama](https://www.together.ai/blog/redpajama-data-v2) [MAP-en](https://arxiv.org/abs/2405.19327)                                                                                                              |
| RuleCharNumber | EFFECTIVENESS     | check whether the number of char > 100                                                | [MAP-en](https://arxiv.org/abs/2405.19327)                                                                                                                                                                          |
| RuleCharSplit | FLUENCY | Check PDF content for abnormally split characters. | |
| RuleColonEnd | COMPLETENESS      | check whether the last char is ':'                                                    |                                                                                                                                                                                                                     |
| RuleContentNull | EFFECTIVENESS     | check whether content is null                                                         |                                                                                                                                                                                                                     |
| RuleContentShort | EFFECTIVENESS | Check whether content is too short. | |
| RuleContentShortMultiLan | EFFECTIVENESS | Check whether multilingual content is too short. | |
| RuleCurlyBracket | UNDERSTANDABILITY | check whether the ratio of the number of {,} and the number of characters < 0.025     | [Redpajama](https://www.together.ai/blog/redpajama-data-v2) [C4](https://arxiv.org/abs/1910.10683)                                                                                                                  |
| RuleDictConsistency | EFFECTIVENESS | Compare two dictionary fields and report mismatched keys. | |
| RuleDocFormulaRepeat | SIMILARITY | Check whether formulas repeat in a document. | |
| RuleDocRepeat | SIMILARITY        | check whether content repeats                                                         | [Redpajama](https://www.together.ai/blog/redpajama-data-v2) [MAP-en](https://arxiv.org/abs/2405.19327) [FineWeb](https://huggingface.co/datasets/HuggingFaceFW/fineweb)  [Gopher](https://arxiv.org/abs/2112.11446) |
| RuleDoi | EFFECTIVENESS | Validate DOI metadata. | |
| RuleEnterAndSpace | EFFECTIVENESS | Check abnormal combinations of line breaks and spaces. | |
| RuleEnterMore | EFFECTIVENESS | Check whether content has excessive consecutive line breaks. | |
| RuleEnterRatioMore | EFFECTIVENESS | Check whether the line-break ratio is excessive. | |
| RuleHallucinationHHEM | HALLUCINATION | Detect ungrounded claims with MiniCheck-Flan-T5-Large (checks whether the response is supported by the context). | |
| RuleHeadWordAr | RELEVANCE | Check Arabic content for irrelevant source information. | |
| RuleHeadWordCs | RELEVANCE | Check Czech content for irrelevant source information. | |
| RuleHeadWordHu | RELEVANCE | Check Hungarian content for irrelevant source information. | |
| RuleHeadWordKo | RELEVANCE | Check Korean content for irrelevant source information. | |
| RuleHeadWordRu | RELEVANCE | Check Russian content for irrelevant source information. | |
| RuleHeadWordSr | RELEVANCE | Check Serbian content for irrelevant source information. | |
| RuleHeadWordTh | RELEVANCE | Check Thai content for irrelevant source information. | |
| RuleHeadWordVi | RELEVANCE | Check Vietnamese content for irrelevant source information. | |
| RuleHtmlEntity | RELEVANCE         | check whether content has html entity                                                 |                                                                                                                                                                                                                     |
| RuleHtmlTag | EFFECTIVENESS | Check whether content contains image links or HTML tags. | |
| RuleIDCard | SECURITY          | check if the content contains ID card.                                                |                                                                                                                                                                                                                     |
| RuleImageArtimuse | IMG_ARTIMUSE | Detect inappropriate artificial-image usage. | |
| RuleImageDataFormat | EFFECTIVENESS | Check whether image data has the expected format. | |
| RuleImageLabelOverlap | IMG_LABEL_OVERLAP | Check whether image labels overlap. | |
| RuleImageLabelVisualization | IMG_LABEL_VISUALIZATION | Visualize and validate image labels. | |
| RuleImageQuality | IMG_EFFECTIVENESS | Check whether image quality meets the configured standard. | |
| RuleImageRepeat | IMG_SIMILARITY | Detect duplicate images using perceptual hash or CNN features. | |
| RuleImageSizeValid | IMG_EFFECTIVENESS | Check whether image dimensions and aspect ratio are valid. | |
| RuleImageTextSimilarity | IMG_RELEVANCE | Check similarity between an image and its text content. | |
| RuleImageValid | IMG_EFFECTIVENESS | Check whether an image is valid and not uniformly white or black. | |
| RuleInvisibleChar | EFFECTIVENESS | Check whether content contains invisible characters. | |
| RuleIsbn | EFFECTIVENESS | Validate ISBN metadata. | |
| RuleLatexSpecialChar | EFFECTIVENESS | Check PDF content for abnormal LaTeX characters. | |
| RuleLineEndWithEllipsis | COMPLETENESS      | check whether the ratio of line ends with ellipsis < 0.3                              | [Redpajama](https://www.together.ai/blog/redpajama-data-v2) [MAP-en](https://arxiv.org/abs/2405.19327) [Gopher](https://arxiv.org/abs/2112.11446) [Dolma](https://arxiv.org/abs/2402.00159)                         |
| RuleLineEndWithTerminal | COMPLETENESS      | check whether the ratio of line ends with terminal punctuation mark > 0.6             | [Redpajama](https://www.together.ai/blog/redpajama-data-v2) [FineWeb](https://huggingface.co/datasets/HuggingFaceFW/fineweb)  [C4](https://arxiv.org/abs/1910.10683)                                                |
| RuleLineJavascriptCount | EFFECTIVENESS     | check whether line with the word Javascript.                                          | [Redpajama](https://www.together.ai/blog/redpajama-data-v2) [FineWeb](https://huggingface.co/datasets/HuggingFaceFW/fineweb)  [C4](https://arxiv.org/abs/1910.10683)                                                |
| RuleLineStartWithBulletpoint | UNDERSTANDABILITY | check whether the ratio of line starts with bullet points < 0.9                       | [Redpajama](https://www.together.ai/blog/redpajama-data-v2) [MAP-en](https://arxiv.org/abs/2405.19327) [Gopher](https://arxiv.org/abs/2112.11446) [Dolma](https://arxiv.org/abs/2402.00159)                         |
| RuleLoremIpsum | EFFECTIVENESS     | check whether the ratio of lorem ipsum < 3e-08                                        | [Redpajama](https://www.together.ai/blog/redpajama-data-v2) [MAP-en](https://arxiv.org/abs/2405.19327) [FineWeb](https://huggingface.co/datasets/HuggingFaceFW/fineweb)  [C4](https://arxiv.org/abs/1910.10683)     |
| RuleMeanWordLength | EFFECTIVENESS     | check whether the mean length of word in [3, 10]                                      | [Redpajama](https://www.together.ai/blog/redpajama-data-v2) [MAP-en](https://arxiv.org/abs/2405.19327) [Gopher](https://arxiv.org/abs/2112.11446) [Dolma](https://arxiv.org/abs/2402.00159)                         |
| RuleMetadataSimilarity | EFFECTIVENESS | Compare the similarity of scientific metadata fields. | |
| RuleNlpDataFormat | EFFECTIVENESS | Check whether NLP data has the expected format. | |
| RuleNoPunc | FLUENCY           | check whether paragraph has no punctuation.                                           |                                                                                                                                                                                                                     |
| RuleOnlyUrl | EFFECTIVENESS | Check whether content consists only of a URL. | |
| RulePatternSearch | RELEVANCE | Search content using a user-provided pattern. | |
| RulePIIDetection | SECURITY | Detect personally identifiable information in text. | |
| RulePatentFieldValidation | EFFECTIVENESS | Validate patent claims length and IPC classification-code format. | |
| RuleQuanliangFieldValidation | EFFECTIVENESS | Validate full-volume scientific metadata fields. | |
| RuleResumeDateFormat | RESUME_DATE | Check whether a resume uses inconsistent date formats. | |
| RuleResumeDetailedAddress | RESUME_PRIVACY | Check whether a resume contains a detailed address. | |
| RuleResumeEducationMissing | RESUME_COMPLETENESS | Check whether a resume is missing its education section. | |
| RuleResumeEmailMissing | RESUME_CONTACT | Check whether a resume is missing an email address. | |
| RuleResumeEmoji | RESUME_PROFESSIONALISM | Check whether a resume contains emoji. | |
| RuleResumeExcessiveWhitespace | RESUME_FORMAT | Check whether a resume contains excessive whitespace. | |
| RuleResumeExperienceMissing | RESUME_COMPLETENESS | Check whether a resume is missing work experience. | |
| RuleResumeIDCard | RESUME_PRIVACY | Check whether a resume contains a Chinese ID card number. | |
| RuleResumeInformal | RESUME_PROFESSIONALISM | Check whether a resume contains informal language. | |
| RuleResumeMarkdown | RESUME_FORMAT | Check whether a resume contains Markdown syntax errors. | |
| RuleResumeNameMissing | RESUME_STRUCTURE | Check whether a resume is missing a name in its first section. | |
| RuleResumePhoneFormat | RESUME_CONTACT | Check whether a phone number has an invalid format. | |
| RuleResumePhoneMissing | RESUME_CONTACT | Check whether a resume is missing a phone number. | |
| RuleResumeSectionMissing | RESUME_STRUCTURE | Check whether a resume is missing required sections. | |
| RuleSentenceNumber | COMPLETENESS      | check whether the number of sentence in [3, 7500]                                     | [Redpajama](https://www.together.ai/blog/redpajama-data-v2) [MAP-en](https://arxiv.org/abs/2405.19327) [FineWeb](https://huggingface.co/datasets/HuggingFaceFW/fineweb) [C4](https://arxiv.org/abs/1910.10683)      |
| RuleSftDataFormat | EFFECTIVENESS | Check whether supervised fine-tuning data has the expected format. | |
| RuleSourceFieldValidation | EFFECTIVENESS | Validate scientific metadata source fields. | |
| RuleSpaceMore | EFFECTIVENESS | Check whether content contains excessive spaces. | |
| RuleSpecialCharacter | RELEVANCE         | check whether content has special characters.                                         |                                                                                                                                                                                                                     |
| RuleStopWord | EFFECTIVENESS     | check whether the ratio of stop word > 0.06                                           | [Redpajama](https://www.together.ai/blog/redpajama-data-v2) [MAP-en](https://arxiv.org/abs/2405.19327) [Gopher](https://arxiv.org/abs/2112.11446) [Dolma](https://arxiv.org/abs/2402.00159)                         |
| RuleSymbolWordRatio | EFFECTIVENESS     | check whether the ratio of symbol / word is > 0.4                                     | [Redpajama](https://www.together.ai/blog/redpajama-data-v2) [Gopher](https://arxiv.org/abs/2112.11446) [Dolma](https://arxiv.org/abs/2402.00159)                                                                    |
| RuleUniqueWords | UNDERSTANDABILITY | check whether the ratio of unique words > 0.1                                         | [Redpajama](https://www.together.ai/blog/redpajama-data-v2) [MAP-en](https://arxiv.org/abs/2405.19327)                                                                                                              |
| RuleUnsafeWords | SECURITY | Check whether content contains unsafe words. | |
| RuleVedioDataFormat | EFFECTIVENESS | Check whether video data has the expected format. | |
| RuleWatermark | RELEVANCE         | check whether content has watermarks.                                                 |                                                                                                                                                                                                                     |
| RuleWordNumber | EFFECTIVENESS     | check whether the number of word in [20, 100000]                                      | [Redpajama](https://www.together.ai/blog/redpajama-data-v2) [MAP-en](https://arxiv.org/abs/2405.19327) [Gopher](https://arxiv.org/abs/2112.11446) [Dolma](https://arxiv.org/abs/2402.00159)                         |
| RuleWordSplit | FLUENCY | Check PDF content for abnormally split words. | |
| RuleWordStuck | FLUENCY | Check whether words are abnormally joined together. | |
