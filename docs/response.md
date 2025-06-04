The specific responses are as follows:

| response name               | description                                                   |
| --------------------------- | ------------------------------------------------------------- |
| ResponseScoreReason         | Used for scenarios that require score and reason.             |
| ResponseNameReason          | Used for scenarios that require name and reason.              |
| ResponseScoreTypeNameReason | Used for scenarios that require score, type, name and reason. |

| required input | type | default | Description                                 |
| -------------- | ---- | ------- | ------------------------------------------- |
| score          | int  | -       | Score defined in prompt. No specific range. |
| type           | str  | Type    | Type defined in prompt.                     |
| name           | str  | Name    | Name defined in prompt.                     |
| reason         | str  | ""      | Reason defined in prompt.                   |
