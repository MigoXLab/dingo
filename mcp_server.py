import json
import os
import uuid
from typing import Literal, Optional, List, Dict

from dingo.exec import Executor
from dingo.io import InputArgs
from dingo.utils import log
from dingo.model import Model
from fastmcp import FastMCP

# Dingo log level can be set via InputArgs('log_level') if needed

mcp = FastMCP("Dingo Evaluator")

PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))

@mcp.tool()
def run_dingo_evaluation(
    input_path: str,
    evaluation_type: Literal["rule", "llm"],
    eval_group_name: str = "",
    output_dir: Optional[str] = None,
    task_name: Optional[str] = None,
    save_data: bool = True,
    save_correct: bool = True,
    kwargs: dict = {}
) -> str:
    """Runs a Dingo evaluation (rule-based or LLM-based).

    Infers data_format from input_path extension (.json, .jsonl, .txt) if not provided in kwargs.
    Defaults dataset to 'local' if input_path is provided and dataset is not in kwargs.
    If output_dir is not specified, creates output relative to input_path.

    Args:
        input_path: Path to the input file or directory.
        evaluation_type: Type of evaluation ('rule' or 'llm').
        eval_group_name: The specific rule group or LLM model name.
                         (Optional when custom_config is provided for LLM evaluations)
        output_dir: Optional directory to save outputs.
        task_name: Optional name for the task.
        save_data: Whether to save the detailed JSONL output (default: True).
        save_correct: Whether to save correct data (default: True).
        kwargs: Dictionary containing additional arguments compatible with dingo.io.InputArgs.
                Use for: dataset, data_format, column_content, column_id,
                column_prompt, column_image, custom_config, max_workers, etc.
                API keys for LLMs should be set via environment variables in mcp.json.

    Returns:
        The absolute path to the primary output file (summary.json or first .jsonl).
    """
    log.info(f"Received Dingo request: type={evaluation_type}, group={eval_group_name}, input={input_path}")

    # --- Path Resolution ---
    abs_input_path = None
    if input_path:
        abs_input_path = os.path.join(PROJECT_ROOT, input_path)
        if not os.path.exists(abs_input_path):
            log.warning(f"Input path '{input_path}' relative to script dir ('{abs_input_path}') not found. Trying relative to CWD or absolute.")
            abs_input_path = os.path.abspath(input_path) # Fallback
            if not os.path.exists(abs_input_path):
                 log.warning(f"Input path '{abs_input_path}' (relative to CWD or absolute) also not found. Dingo validation may fail.")
        abs_input_path = abs_input_path.replace("\\", "/")
        log.info(f"Using resolved input path: {abs_input_path}")

    # --- Data Format Inference ---
    inferred_data_format = None
    if 'data_format' not in kwargs and input_path:
        _, ext = os.path.splitext(input_path)
        ext = ext.lower()
        if ext == '.jsonl': inferred_data_format = 'jsonl'
        elif ext == '.json': inferred_data_format = 'json'
        elif ext == '.txt': inferred_data_format = 'plaintext'
        if inferred_data_format: log.info(f"Inferred data_format: '{inferred_data_format}'")

    # --- Custom Config Handling ---
    custom_config_input = kwargs.get('custom_config')
    loaded_custom_config = None
    if custom_config_input:
        if isinstance(custom_config_input, str):
            potential_path = os.path.join(PROJECT_ROOT, custom_config_input)
            if not os.path.exists(potential_path): potential_path = os.path.abspath(custom_config_input)

            if os.path.exists(potential_path):
                try:
                    abs_config_path_str = potential_path.replace("\\", "/")
                    log.info(f"Loading custom config from file: {abs_config_path_str}")
                    with open(abs_config_path_str, 'r', encoding='utf-8') as f:
                        loaded_custom_config = json.load(f)
                except Exception as e:
                    log.error(f"Failed to load custom config file '{abs_config_path_str}': {e}", exc_info=True)
                    raise ValueError(f"Failed to load custom config file: {e}") from e
            else:
                try:
                    log.info("Parsing custom_config kwarg as JSON string.")
                    loaded_custom_config = json.loads(custom_config_input)
                except json.JSONDecodeError as e:
                    log.error(f"custom_config kwarg is not a valid path or file and failed to parse as JSON: {e}", exc_info=True)
                    raise ValueError(f"Invalid custom_config: Not a path or valid JSON string.") from e
        elif isinstance(custom_config_input, dict):
             log.info("Using custom_config kwarg directly as dictionary.")
             loaded_custom_config = custom_config_input
        else:
             raise ValueError("custom_config must be a file path (str), a JSON string (str), or a dictionary.")

    # --- Attempt to normalize custom_config if it looks like the LLM-generated structure ---
    if isinstance(loaded_custom_config, dict) and 'llm_eval' in loaded_custom_config:
        log.warning("Detected 'llm_eval' key in custom_config. Attempting to normalize structure.")
        try:
            original_config = loaded_custom_config
            normalized_config = {}
            llm_eval_section = original_config.get('llm_eval', {})

            # Extract prompts
            prompts = []
            evaluations = llm_eval_section.get('evaluations', [])
            if evaluations and isinstance(evaluations, list):
                first_eval = evaluations[0]
                if isinstance(first_eval, dict) and 'prompt' in first_eval and isinstance(first_eval['prompt'], dict) and 'name' in first_eval['prompt']:
                    prompts.append(first_eval['prompt']['name'])
                # Note: This only extracts the prompt from the *first* evaluation entry
            if prompts:
                normalized_config['prompt_list'] = prompts
                log.info(f"Normalized prompt_list: {prompts}")
            else:
                 log.warning("Could not extract prompt name(s) for normalization.")

            # Extract llm_config
            models_section = llm_eval_section.get('models', {})
            if models_section and isinstance(models_section, dict):
                # Assume the first key in 'models' is the one we want for llm_config
                model_name = next(iter(models_section), None)
                if model_name:
                    model_details = models_section[model_name]
                    # Map api_key -> key if necessary
                    if 'api_key' in model_details and 'key' not in model_details:
                        model_details['key'] = model_details.pop('api_key')
                    normalized_config['llm_config'] = {model_name: model_details}
                    log.info(f"Normalized llm_config for model '{model_name}': {model_details}")
                else:
                    log.warning("Could not extract model details for normalization.")

            if 'prompt_list' in normalized_config and 'llm_config' in normalized_config:
                loaded_custom_config = normalized_config
                log.info("Successfully normalized custom_config structure.")
            else:
                log.warning("Normalization failed to produce expected keys. Using original structure.")
                loaded_custom_config = original_config # Revert if normalization failed

        except Exception as e:
            log.error(f"Error during custom_config normalization: {e}. Using original structure.", exc_info=True)
            # Keep original config if normalization fails

    # --- Determine Output Path ---
    task_name_for_path = task_name if task_name else f"mcp_eval_{uuid.uuid4().hex[:8]}"
    if output_dir:
        abs_output_dir = os.path.abspath(output_dir)
        log.info(f"Using custom output directory: {abs_output_dir}")
    else:
        if not abs_input_path:
             raise ValueError("Cannot determine default output directory without an input_path.")
        input_parent_dir = os.path.dirname(abs_input_path)
        abs_output_dir = os.path.join(input_parent_dir, f"dingo_output_{task_name_for_path}")
        abs_output_dir = abs_output_dir.replace("\\","/")
        log.info(f"Using default output directory relative to input: {abs_output_dir}")

    os.makedirs(abs_output_dir, exist_ok=True)

    # --- Prepare Dingo InputArgs Data ---
    final_dataset_type = kwargs.get('dataset') if 'dataset' in kwargs else ('local' if abs_input_path else 'hugging_face')
    final_data_format = kwargs.get('data_format', inferred_data_format)
    final_task_name = task_name if task_name else task_name_for_path
    log.info(f"Final dataset='{final_dataset_type}', data_format='{final_data_format if final_data_format else '(Dingo default)'}'")

    # Start with fixed args + defaults + derived values
    input_data = {
        "output_path": abs_output_dir,
        "task_name": final_task_name,
        "save_data": save_data,
        "save_correct": save_correct,
        "input_path": abs_input_path,
        "dataset": final_dataset_type,
        "custom_config": loaded_custom_config,
        "data_format": final_data_format,
        "max_workers": kwargs.get('max_workers', 1), # Defaulting to 1 for MCP stability
        "batch_size": kwargs.get('batch_size', 1),   # Defaulting to 1 for MCP stability
    }

    # --- Handle eval_group_name based on evaluation type ---
    input_data["eval_group"] = None  # Initialize to None
    valid_rule_groups = {'default', 'sft', 'pretrain'}

    if evaluation_type == "rule":
        # Check if eval_group_name is provided and valid, otherwise default
        if eval_group_name and eval_group_name in valid_rule_groups:
            input_data["eval_group"] = eval_group_name
            log.info(f"Using provided rule group: {eval_group_name}")
        elif eval_group_name: # Provided but invalid
             log.warning(f"Invalid rule group name '{eval_group_name}' provided. Valid options are: {valid_rule_groups}. Defaulting to 'default'.")
             input_data["eval_group"] = "default"
        else: # Not provided (eval_group_name is "")
            log.info("No rule group name provided. Defaulting to 'default'.")
            input_data["eval_group"] = "default"
    elif evaluation_type == "llm":
        log.info("LLM evaluation type selected. 'eval_group_name' will not be explicitly set; handled by Dingo based on custom_config.")
        # Check if the default empty string was overridden
        if eval_group_name:
            log.warning(f"'eval_group_name' ('{eval_group_name}') provided for LLM evaluation, but it will be ignored.")

    # Merge valid InputArgs fields from kwargs, logging ignored keys
    processed_args = set(input_data.keys())
    log.debug(f"Checking kwargs for additional InputArgs: {list(kwargs.keys())}")
    for k, v in kwargs.items():
        if k in processed_args:
            log.warning(f"Argument '{k}' from kwargs ignored (already handled). Value provided: {v}")
            continue
        if k in InputArgs.model_fields:
            log.debug(f"Adding '{k}={v}' from kwargs to InputArgs data.")
            input_data[k] = v
        else:
            log.warning(f"Argument '{k}' from kwargs is not a valid Dingo InputArgs field; ignored. Value provided: {v}")

    # Final checks
    if input_data.get("dataset") == 'local' and not input_data.get("input_path"):
         raise ValueError("input_path is required when dataset is 'local'.")

    input_data = {k: v for k, v in input_data.items() if v is not None}

    # --- Execute Dingo ---
    try:
        log.info(f"Initializing Dingo InputArgs...")
        input_args = InputArgs(**input_data)

        executor = Executor.exec_map['local'](input_args)
        log.info(f"Executing Dingo evaluation...")
        result = executor.execute()
        log.info(f"Dingo execution finished.")

        if not hasattr(result, 'output_path') or not result.output_path:
             log.error(f"Evaluation result missing valid 'output_path' attribute.")
             raise RuntimeError("Dingo execution finished, but couldn't determine output path.")

        result_output_dir = result.output_path
        log.info(f"Dingo reported output directory: {result_output_dir}")

        if not os.path.isdir(result_output_dir):
             log.error(f"Output directory from Dingo ({result_output_dir}) does not exist.")
             # Fallback: Return the parent dir used in InputArgs
             log.warning(f"Returning the base output directory used in InputArgs: {abs_output_dir}")
             return abs_output_dir

        # --- Find Primary Output File ---
        # Priority 1: summary.json
        summary_path = os.path.join(result_output_dir, "summary.json")
        if os.path.isfile(summary_path):
             summary_path_abs = os.path.abspath(summary_path).replace("\\", "/")
             log.info(f"Found summary.json. Returning path: {summary_path_abs}")
             return summary_path_abs
        else:
            log.warning(f"summary.json not found in {result_output_dir}. Searching recursively for first .jsonl file...")
            # Priority 2: First .jsonl file recursively
            first_jsonl_path = None
            for root, _, files in os.walk(result_output_dir):
                for file in files:
                    if file.endswith(".jsonl"):
                        first_jsonl_path = os.path.join(root, file).replace("\\", "/")
                        log.info(f"Found first .jsonl: {first_jsonl_path}. Returning this path.")
                        break
                if first_jsonl_path: break

            if first_jsonl_path:
                return first_jsonl_path
            else:
                # Priority 3: Fallback to directory
                log.error(f"Could not find summary.json or any .jsonl files within {result_output_dir}. Returning directory path.")
                result_output_dir_abs = os.path.abspath(result_output_dir).replace("\\", "/")
                return result_output_dir_abs

    except Exception as e:
        log.error(f"Dingo evaluation failed: {e}", exc_info=True)
        raise RuntimeError(f"Dingo evaluation failed: {e}") from e

@mcp.tool()
def list_dingo_components() -> Dict[str, List[str]]:
    """Lists available Dingo rule groups and registered LLM model identifiers.

    Ensures all models are loaded before retrieving the lists.

    Returns:
        A dictionary containing 'rule_groups' and 'llm_models'.
    """
    log.info("Received request to list Dingo components.")
    try:
        Model.load_model() # Ensure all modules are loaded and components registered

        rule_groups = list(Model.get_rule_groups().keys())
        log.info(f"Found rule groups: {rule_groups}")

        llm_models = list(Model.get_llm_name_map().keys())
        log.info(f"Found LLM models: {llm_models}")

        return {
            "rule_groups": rule_groups,
            "llm_models": llm_models
        }
    except Exception as e:
        log.error(f"Failed to list Dingo components: {e}", exc_info=True)
        # Re-raise or return an error structure appropriate for MCP
        raise RuntimeError(f"Failed to list Dingo components: {e}") from e

if __name__ == "__main__":
    mcp.run(transport="sse")
