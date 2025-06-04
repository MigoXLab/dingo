import json
import os
import uuid
from typing import Any, Dict, List, Literal, Optional, Tuple

from dingo.exec import Executor
from dingo.io import InputArgs
from dingo.model import Model
from dingo.utils import log
from fastmcp import FastMCP

# Configure logging based on environment variable
log_level = os.environ.get('LOG_LEVEL', 'info').upper()
log.setLevel(log_level)
log.info(f"Setting Dingo log level to: {log_level}")

# Constants
PROMPT_PREVIEW_MAX_LENGTH = 100  # Maximum length for prompt content preview

# Mapping of LLM classes to their default prompts when no specific prompt is available
DEFAULT_LLM_PROMPTS = {
    'LLMText3H': 'PromptTextHarmless',
    'LLMSecurity': 'PromptProhibition',
    # Add other default mappings as needed
}

# Read environment variables for defaults
DEFAULT_OUTPUT_DIR = os.environ.get('DEFAULT_OUTPUT_DIR')
DEFAULT_MAX_WORKERS = int(os.environ.get('DEFAULT_MAX_WORKERS', '1'))
DEFAULT_BATCH_SIZE = int(os.environ.get('DEFAULT_BATCH_SIZE', '1'))
DEFAULT_SAVE_DATA = os.environ.get('DEFAULT_SAVE_DATA', 'true').lower() == 'true'
DEFAULT_SAVE_CORRECT = os.environ.get('DEFAULT_SAVE_CORRECT', 'true').lower() == 'true'
DEFAULT_DATA_FORMAT = os.environ.get('DEFAULT_DATA_FORMAT')
DEFAULT_DATASET_TYPE = os.environ.get('DEFAULT_DATASET_TYPE', 'local')

log.info(
    f"Environment settings: MAX_WORKERS={DEFAULT_MAX_WORKERS}, BATCH_SIZE={DEFAULT_BATCH_SIZE}, "
    f"SAVE_DATA={DEFAULT_SAVE_DATA}, SAVE_CORRECT={DEFAULT_SAVE_CORRECT}, "
    f"DATA_FORMAT={DEFAULT_DATA_FORMAT}, DATASET_TYPE={DEFAULT_DATASET_TYPE}, "
    f"OUTPUT_DIR={DEFAULT_OUTPUT_DIR}"
)

mcp = FastMCP('Dingo Evaluator')

PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))


# --- Configuration Management Functions ---


def get_llm_config_from_env(eval_group_name: str = '') -> Dict:
    """Get LLM configuration from environment variables and build
    custom_config.

    Args:
        eval_group_name: LLM model name or prompt name, used to select appropriate configuration.

    Returns:
        Dictionary containing LLM configuration.
    """
    config = {}

    # Build OpenAI configuration
    openai_key = os.environ.get('OPENAI_API_KEY')
    openai_base_url = os.environ.get('OPENAI_BASE_URL', 'https://api.openai.com/v1')
    openai_model = os.environ.get('OPENAI_MODEL', 'gpt-4')

    if openai_key:
        # Use eval_group_name as key for llm_config, or default if not provided
        llm_name = eval_group_name if eval_group_name else 'LLMTextQualityModelBase'
        config['llm_config'] = {
            llm_name: {  # Use LLM class name as key
                'key': openai_key,
                'api_url': openai_base_url,
                'model': openai_model,
                'parameters': {
                    'temperature': 0.3,
                    'top_p': 1,
                    'max_tokens': 4000,
                },
            }
        }

    # Build Anthropic configuration
    anthropic_key = os.environ.get('ANTHROPIC_API_KEY')
    anthropic_base_url = os.environ.get('ANTHROPIC_BASE_URL')
    anthropic_model = os.environ.get('ANTHROPIC_MODEL')

    if anthropic_key:
        if 'llm_config' not in config:
            config['llm_config'] = {}
        llm_name = eval_group_name if eval_group_name else 'LLMTextQualityModelBase'
        config['llm_config'][llm_name] = {'key': anthropic_key}
        if anthropic_base_url:
            config['llm_config'][llm_name]['api_url'] = anthropic_base_url
        if anthropic_model:
            config['llm_config'][llm_name]['model'] = anthropic_model

    # If eval_group_name is specified, add it to prompt_list
    if eval_group_name:
        # First try to find associated prompt if eval_group_name is an LLM name
        prompt_name = get_prompt_for_llm(eval_group_name)

        if prompt_name:
            config['prompt_list'] = [prompt_name]
            log.info(f"Using prompt '{prompt_name}' for evaluation with LLM '{eval_group_name}'")
        else:
            # Check if it's directly a valid prompt name
            try:
                Model.load_model()
                if eval_group_name in Model.prompt_name_map:
                    config['prompt_list'] = [eval_group_name]
                    log.info(f"Using prompt '{eval_group_name}' for evaluation")
                else:
                    log.warning(f"'{eval_group_name}' is not a valid prompt name and no associated prompt found")
            except Exception as e:
                log.warning(f"Failed to check if '{eval_group_name}' is a valid prompt: {e}")

    return config


def update_llm_config_with_env(custom_config: Dict) -> Dict:
    """Update existing LLM configuration with values from environment
    variables.

    Args:
        custom_config: Existing LLM configuration dictionary.

    Returns:
        Updated configuration dictionary.
    """
    if not isinstance(custom_config, dict) or 'llm_config' not in custom_config:
        return custom_config

    for llm_name, llm_settings in custom_config['llm_config'].items():
        # Add API key if missing but available in environment
        if 'key' not in llm_settings:
            env_key = os.environ.get(f"{llm_name.upper()}_API_KEY")
            if env_key:
                llm_settings['key'] = env_key
                log.info(f"Added API key for {llm_name} from environment variables")

        # Add API URL if missing but available in environment
        if 'api_url' not in llm_settings:
            env_url = os.environ.get(f"{llm_name.upper()}_BASE_URL")
            if env_url:
                llm_settings['api_url'] = env_url
                log.info(f"Added API URL for {llm_name} from environment variables")

    return custom_config


def normalize_custom_config(config: Dict) -> Dict:
    """Normalize custom_config if it has an LLM-generated structure.

    Args:
        config: Original configuration dictionary.

    Returns:
        Normalized configuration dictionary.
    """
    if not isinstance(config, dict) or 'llm_eval' not in config:
        return config

    log.warning("Detected 'llm_eval' key in custom_config. Attempting to normalize structure.")
    try:
        normalized_config = {}
        llm_eval_section = config.get('llm_eval', {})

        # Extract prompts
        prompts = []
        evaluations = llm_eval_section.get('evaluations', [])
        if evaluations and isinstance(evaluations, list):
            first_eval = evaluations[0]
            if (
                isinstance(first_eval, dict)
                and 'prompt' in first_eval
                and isinstance(first_eval['prompt'], dict)
                and 'name' in first_eval['prompt']
            ):
                prompts.append(first_eval['prompt']['name'])

        if prompts:
            normalized_config['prompt_list'] = prompts
            log.info(f"Normalized prompt_list: {prompts}")
        else:
            log.warning('Could not extract prompt name(s) for normalization.')

        # Extract llm_config
        models_section = llm_eval_section.get('models', {})
        if models_section and isinstance(models_section, dict):
            model_name = next(iter(models_section), None)
            if model_name:
                model_details = models_section[model_name]
                if 'api_key' in model_details and 'key' not in model_details:
                    model_details['key'] = model_details.pop('api_key')
                normalized_config['llm_config'] = {model_name: model_details}
                log.info(f"Normalized llm_config for model '{model_name}'")
            else:
                log.warning('Could not extract model details for normalization.')

        if 'prompt_list' in normalized_config and 'llm_config' in normalized_config:
            log.info('Successfully normalized custom_config structure.')
            return normalized_config
        else:
            log.warning('Normalization failed to produce expected keys. Using original structure.')
            return config

    except Exception as e:
        log.error(f"Error during custom_config normalization: {e}. Using original structure.", exc_info=True)
        return config


def load_custom_config(config_input: Any) -> Optional[Dict]:
    """Load custom configuration from file path, JSON string, or dictionary.

    Args:
        config_input: Configuration input (file path, JSON string, or dictionary).

    Returns:
        Loaded configuration dictionary or None if loading fails.
    """
    if not config_input:
        return None

    loaded_config = None

    if isinstance(config_input, str):
        potential_path = os.path.join(PROJECT_ROOT, config_input)
        if not os.path.exists(potential_path):
            potential_path = os.path.abspath(config_input)

        if os.path.exists(potential_path):
            try:
                abs_config_path_str = potential_path.replace('\\', '/')
                log.info(f"Loading custom config from file: {abs_config_path_str}")
                with open(abs_config_path_str, 'r', encoding='utf-8') as f:
                    loaded_config = json.load(f)
            except Exception as e:
                log.error(f"Failed to load custom config file '{potential_path}': {e}", exc_info=True)
                raise ValueError(f"Failed to load custom config file: {e}") from e
        else:
            try:
                log.info('Parsing custom_config kwarg as JSON string.')
                loaded_config = json.loads(config_input)
            except json.JSONDecodeError as e:
                log.error(f"custom_config not a valid path and failed to parse as JSON: {e}", exc_info=True)
                raise ValueError(f"Invalid custom_config: Not a path or valid JSON string.") from e
    elif isinstance(config_input, dict):
        log.info('Using custom_config kwarg directly as dictionary.')
        loaded_config = config_input
    else:
        raise ValueError('custom_config must be a file path (str), a JSON string (str), or a dictionary.')

    # Normalize config if needed
    if loaded_config:
        loaded_config = normalize_custom_config(loaded_config)

    return loaded_config


def prepare_llm_configuration(evaluation_type: str, eval_group_name: str, kwargs: Dict) -> Dict:
    """Prepare LLM configuration for Dingo evaluation.

    This function handles all aspects of LLM configuration including:
    - Getting config from environment variables
    - Merging with existing configuration
    - Ensuring prompt_list exists and is properly set
    - Handling LLMs without default prompts

    Args:
        evaluation_type: Type of evaluation ('rule' or 'llm')
        eval_group_name: LLM model name or prompt name
        kwargs: Dictionary containing additional arguments

    Returns:
        Updated kwargs dictionary with proper LLM configuration
    """
    if evaluation_type != 'llm':
        return kwargs

    # Get LLM config from environment
    llm_config = get_llm_config_from_env(eval_group_name)
    if llm_config:
        log.info('LLM configuration found in environment variables')
        if 'custom_config' not in kwargs:
            kwargs['custom_config'] = llm_config
            log.info('Using LLM configuration from environment variables')
        elif isinstance(kwargs['custom_config'], dict):
            # Merge custom_config
            for key, value in llm_config.items():
                if key not in kwargs['custom_config']:
                    kwargs['custom_config'][key] = value
                    log.info(f"Adding {key} from environment variables to custom_config")
                elif key == 'prompt_list' and value:
                    # Ensure prompt_list from eval_group_name is included
                    if 'prompt_list' not in kwargs['custom_config']:
                        kwargs['custom_config']['prompt_list'] = value
                    elif value[0] not in kwargs['custom_config']['prompt_list']:
                        kwargs['custom_config']['prompt_list'].extend(value)
                    log.info(f"Updated prompt_list in custom_config: {kwargs['custom_config']['prompt_list']}")

        # Update existing llm_config with API keys from environment
        if isinstance(kwargs.get('custom_config'), dict) and 'llm_config' in kwargs['custom_config']:
            kwargs['custom_config'] = update_llm_config_with_env(kwargs['custom_config'])

    # Ensure prompt_list exists in custom_config for LLM evaluation
    if not kwargs.get('custom_config', {}).get('prompt_list'):
        if eval_group_name:
            # Try to find associated prompt if eval_group_name is an LLM name
            prompt_name = get_prompt_for_llm(eval_group_name)

            if prompt_name:
                kwargs['custom_config'] = kwargs.get('custom_config', {})
                kwargs['custom_config']['prompt_list'] = [prompt_name]
                log.info(f"Setting prompt_list to [{prompt_name}] based on LLM '{eval_group_name}'")
            else:
                # Handle specific LLM classes that don't have default prompts in their class definitions.
                # Some LLM implementations (like LLMText3H and LLMSecurity) don't define the 'prompt'
                # attribute that would normally link them to their default prompts. We need to manually
                # assign appropriate prompts to these LLMs to ensure proper evaluation.
                if eval_group_name in DEFAULT_LLM_PROMPTS:
                    default_prompt = DEFAULT_LLM_PROMPTS[eval_group_name]
                    kwargs['custom_config'] = kwargs.get('custom_config', {})
                    kwargs['custom_config']['prompt_list'] = [default_prompt]
                    log.info(f"Setting default prompt '{default_prompt}' for LLM '{eval_group_name}'")
                else:
                    # Get available prompts for better error message
                    try:
                        Model.load_model()
                        available_prompts = list(Model.prompt_name_map.keys())
                        prompt_examples = (
                            ', '.join(available_prompts[:5]) + '...'
                            if len(available_prompts) > 5
                            else ', '.join(available_prompts)
                        )

                        error_msg = (
                            f"No valid prompt found for '{eval_group_name}'. For LLM evaluation, please provide "
                            f"a valid prompt name. Available prompts include: {prompt_examples}. "
                            f"Use 'list_dingo_components(component_type=\"prompts\")' to see all available prompts."
                        )
                        log.error(error_msg)
                        raise ValueError(error_msg)
                    except Exception as e:
                        log.error(f"Failed to get available prompts: {e}", exc_info=True)
                        raise ValueError(
                            f"No valid prompt found for '{eval_group_name}'. For LLM evaluation, please provide a valid prompt name."
                        )
        else:
            log.error('No prompt_list found in custom_config and no eval_group_name provided')
            raise ValueError(
                'For LLM evaluation, either prompt_list in custom_config or eval_group_name must be provided'
            )

    return kwargs


# --- Path and File Handling Functions ---


def resolve_input_path(input_path: str) -> Optional[str]:
    """Resolve and validate input file path.

    Args:
        input_path: Relative or absolute path to input file.

    Returns:
        Absolute path to input file or None if path doesn't exist.
    """
    if not input_path:
        return None

    abs_input_path = os.path.join(PROJECT_ROOT, input_path)
    if not os.path.exists(abs_input_path):
        log.warning(f"Input path relative to script dir not found. Trying relative to CWD or absolute.")
        abs_input_path = os.path.abspath(input_path)  # Fallback
        if not os.path.exists(abs_input_path):
            log.warning(f"Input path not found. Dingo validation may fail.")

    return abs_input_path.replace('\\', '/')


def infer_data_format(input_path: str) -> Optional[str]:
    """Infer data format from file extension.

    Args:
        input_path: Path to input file.

    Returns:
        Inferred data format or None if format can't be determined.
    """
    if not input_path:
        return None

    _, ext = os.path.splitext(input_path)
    ext = ext.lower()

    format_map = {'.jsonl': 'jsonl', '.json': 'json', '.txt': 'plaintext'}

    inferred_format = format_map.get(ext)
    if inferred_format:
        log.info(f"Inferred data_format: '{inferred_format}'")

    return inferred_format


def determine_output_dir(input_path: str, task_name: str, output_dir: Optional[str] = None) -> str:
    """Determine output directory based on input parameters and defaults.

    Args:
        input_path: Path to input file.
        task_name: Name of the task.
        output_dir: Explicitly provided output directory.

    Returns:
        Absolute path to output directory.
    """
    if output_dir:
        abs_output_dir = os.path.abspath(output_dir)
        log.info(f"Using custom output directory: {abs_output_dir}")
    elif DEFAULT_OUTPUT_DIR:
        abs_output_dir = os.path.join(DEFAULT_OUTPUT_DIR, task_name)
        abs_output_dir = abs_output_dir.replace('\\', '/')
        log.info(f"Using environment default output directory: {abs_output_dir}")
    else:
        if not input_path:
            raise ValueError('Cannot determine output directory without an input_path.')
        input_parent_dir = os.path.dirname(input_path)
        abs_output_dir = os.path.join(input_parent_dir, f"dingo_output_{task_name}")
        abs_output_dir = abs_output_dir.replace('\\', '/')
        log.info(f"Using default output directory relative to input: {abs_output_dir}")

    os.makedirs(abs_output_dir, exist_ok=True)
    return abs_output_dir


def find_result_file(result_output_dir: str) -> Tuple[Optional[str], Optional[str]]:
    """Find the primary result file in the output directory.

    Args:
        result_output_dir: Output directory to search.

    Returns:
        Tuple of (file path, file content) if found, otherwise (None, None).
    """
    if not os.path.isdir(result_output_dir):
        log.error(f"Output directory {result_output_dir} does not exist.")
        return None, None

    result_file_path = None
    file_content = None

    # Priority 1: summary.json
    summary_path = os.path.join(result_output_dir, 'summary.json')
    if os.path.isfile(summary_path):
        result_file_path = os.path.abspath(summary_path).replace('\\', '/')
        log.info(f"Found summary.json at: {result_file_path}")
    else:
        log.warning(f"summary.json not found. Searching recursively for first .jsonl file...")
        # Priority 2: First .jsonl file recursively
        for root, _, files in os.walk(result_output_dir):
            for file in files:
                if file.endswith('.jsonl'):
                    result_file_path = os.path.join(root, file).replace('\\', '/')
                    log.info(f"Found first .jsonl at: {result_file_path}")
                    break
            if result_file_path:
                break

    # If in Smithery mode, read file content
    if os.environ.get('LOCAL_DEPLOYMENT_MODE') == 'true' and result_file_path:
        try:
            with open(result_file_path, 'r', encoding='utf-8') as f:
                file_content = f.read()
            log.info(f"Successfully read content from {result_file_path}")
        except Exception as e:
            log.error(f"Failed to read content from {result_file_path}: {e}", exc_info=True)
            file_content = f"Error reading result file: {e}\nFile path: {result_file_path}"

    return result_file_path, file_content


# --- MCP API Functions ---


@mcp.tool()
def run_dingo_evaluation(
    input_path: str, evaluation_type: Literal['rule', 'llm'] = 'rule', eval_group_name: str = '', kwargs: dict = {}
) -> str:
    """Runs a Dingo evaluation (rule-based or LLM-based) on a file.

    Infers data_format from input_path extension (.json, .jsonl, .txt) if not provided in kwargs.
    Defaults dataset to 'local' if input_path is provided and dataset is not in kwargs.
    If output_dir is not specified via kwargs or environment variables, creates output relative to input_path.
    API keys for LLMs should be set via environment variables in mcp.json or system environment.

    Args:
        input_path: Path to the input file or directory.
        evaluation_type: Type of evaluation ('rule' or 'llm'), defaults to 'rule'.
        eval_group_name: The specific rule group or LLM model name.
                         Defaults to empty, Dingo will use 'default' for rules or infer from custom_config for LLMs.
                         (Optional when custom_config is provided for LLM evaluations via kwargs)
        kwargs: Dictionary containing additional arguments compatible with dingo.io.InputArgs.
                Use for: output_dir, task_name, save_data, save_correct, dataset, data_format,
                column_content, column_id, column_prompt, column_image, custom_config,
                max_workers, batch_size, etc.

    Returns:
        For Smithery deployment: The content of the result file (summary.json or first .jsonl)
        Otherwise: The absolute path to the primary output file (summary.json or first .jsonl).
    """
    log.info(f"Received Dingo request: type={evaluation_type}, group={eval_group_name}, input={input_path}")

    # --- Handle Input Path ---
    abs_input_path = resolve_input_path(input_path)
    if abs_input_path:
        log.info(f"Using resolved input path: {abs_input_path}")

    # --- Handle LLM Configuration ---
    if evaluation_type == 'llm':
        kwargs = prepare_llm_configuration(evaluation_type, eval_group_name, kwargs)

    # --- Data Format Inference ---
    inferred_data_format = infer_data_format(input_path)

    # --- Custom Config Handling ---
    custom_config_input = kwargs.get('custom_config')
    loaded_custom_config = load_custom_config(custom_config_input)

    # --- Determine Output Path ---
    task_name_from_kwargs = kwargs.get('task_name')
    output_dir_from_kwargs = kwargs.get('output_dir')

    task_name_for_path = task_name_from_kwargs if task_name_from_kwargs else f"mcp_eval_{uuid.uuid4().hex[:8]}"
    abs_output_dir = determine_output_dir(abs_input_path, task_name_for_path, output_dir_from_kwargs)

    # --- Prepare Dingo InputArgs Data ---
    final_dataset_type = kwargs.get('dataset', DEFAULT_DATASET_TYPE if 'dataset' not in kwargs else None)
    final_data_format = kwargs.get('data_format', inferred_data_format if inferred_data_format else DEFAULT_DATA_FORMAT)
    final_task_name = task_name_from_kwargs if task_name_from_kwargs else task_name_for_path
    final_save_data = kwargs.get('save_data') if kwargs.get('save_data') is not None else DEFAULT_SAVE_DATA
    final_save_correct = kwargs.get('save_correct') if kwargs.get('save_correct') is not None else DEFAULT_SAVE_CORRECT
    final_max_workers = kwargs.get('max_workers', DEFAULT_MAX_WORKERS)
    final_batch_size = kwargs.get('batch_size', DEFAULT_BATCH_SIZE)

    log.info(
        f"Final dataset='{final_dataset_type}', data_format='{final_data_format if final_data_format else '(Dingo default)'}', "
        f"save_data={final_save_data}, save_correct={final_save_correct}, "
        f"max_workers={final_max_workers}, batch_size={final_batch_size}"
    )

    # Start with fixed args + defaults + derived values
    input_data = {
        'output_path': abs_output_dir,
        'task_name': final_task_name,
        'save_data': final_save_data,
        'save_correct': final_save_correct,
        'input_path': abs_input_path,
        'dataset': final_dataset_type,
        'custom_config': loaded_custom_config,
        'data_format': final_data_format,
        'max_workers': final_max_workers,
        'batch_size': final_batch_size,
    }

    # --- Handle eval_group_name based on evaluation type ---
    input_data['eval_group'] = None  # Initialize to None
    valid_rule_groups = {'default', 'sft', 'pretrain'}

    if evaluation_type == 'rule':
        # Check if eval_group_name is provided and valid, otherwise default
        if eval_group_name and eval_group_name in valid_rule_groups:
            input_data['eval_group'] = eval_group_name
            log.info(f"Using provided rule group: {eval_group_name}")
        elif eval_group_name:  # Provided but invalid
            log.warning(
                f"Invalid rule group name '{eval_group_name}'. Valid options: {valid_rule_groups}. Defaulting to 'default'."
            )
            input_data['eval_group'] = 'default'
        else:  # Not provided (eval_group_name is "")
            log.info("No rule group name provided. Defaulting to 'default'.")
            input_data['eval_group'] = 'default'
    elif evaluation_type == 'llm':
        log.info("LLM evaluation type selected. 'eval_group_name' handled by Dingo based on custom_config.")
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
            log.warning(f"Argument '{k}' from kwargs is not a valid Dingo InputArgs field; ignored. Value: {v}")

    # Final checks
    if input_data.get('dataset') == 'local' and not input_data.get('input_path'):
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

        result_file_path, file_content = find_result_file(result_output_dir)

        # Return content in Smithery mode, path otherwise
        if os.environ.get('LOCAL_DEPLOYMENT_MODE') == 'true':
            if file_content:
                return file_content
            else:
                return f"No result file found. Output directory: {result_output_dir}"
        else:
            if result_file_path:
                return result_file_path
            else:
                result_output_dir_abs = os.path.abspath(result_output_dir).replace('\\', '/')
                log.warning(f"No result file found. Returning directory path: {result_output_dir_abs}")
                return result_output_dir_abs

    except Exception as e:
        log.error(f"Dingo evaluation failed: {e}", exc_info=True)
        raise RuntimeError(f"Dingo evaluation failed: {e}") from e


def _get_rule_groups_info(include_details: bool = False) -> Dict[str, List]:
    """Helper function to get rule groups information.

    Args:
        include_details: Whether to include detailed information about each rule group.

    Returns:
        Dictionary with rule groups information.
    """
    rule_groups = list(Model.get_rule_groups().keys())
    log.info(f"Found rule groups: {rule_groups}")

    if include_details:
        rule_details = []
        for rg in rule_groups:
            details = get_rule_details(rg)
            rule_details.append(details)
        return {'rule_groups': rule_details}
    else:
        return {'rule_groups': rule_groups}


def _get_llm_models_info(include_details: bool = False) -> Dict[str, List]:
    """Helper function to get LLM models information.

    Args:
        include_details: Whether to include detailed information about each LLM model.

    Returns:
        Dictionary with LLM models information.
    """
    llm_models = list(Model.get_llm_name_map().keys())
    log.info(f"Found LLM models: {llm_models}")

    result = {}

    if include_details:
        llm_details = []
        for lm in llm_models:
            details = get_llm_details(lm)

            # Add associated prompt information
            prompt_name = get_prompt_for_llm(lm)
            if prompt_name:
                details['associated_prompt'] = prompt_name

            llm_details.append(details)
        result['llm_models'] = llm_details

        # Add LLM to Prompt mapping
        llm_prompt_map = {}
        for lm in llm_models:
            prompt_name = get_prompt_for_llm(lm)
            if prompt_name:
                llm_prompt_map[lm] = prompt_name

        if llm_prompt_map:
            result['llm_prompt_mappings'] = llm_prompt_map
    else:
        result['llm_models'] = llm_models

    return result


def _get_prompts_info(include_details: bool = False) -> Dict[str, List]:
    """Helper function to get prompts information.

    Args:
        include_details: Whether to include detailed information about each prompt.

    Returns:
        Dictionary with prompts information.
    """
    prompts = list(Model.prompt_name_map.keys())
    log.info(f"Found prompts: {prompts}")

    if include_details:
        prompt_details = []
        for p in prompts:
            details = get_prompt_details(p)
            prompt_details.append(details)
        return {'prompts': prompt_details}
    else:
        return {'prompts': prompts}


@mcp.tool()
def list_dingo_components(
    component_type: Literal['rule_groups', 'llm_models', 'prompts', 'all'] = 'all', include_details: bool = False
) -> Dict[str, List]:
    """Lists available Dingo rule groups, registered LLM model identifiers, and
    prompt definitions.

    Ensures all models are loaded before retrieving the lists.
    If include_details is True, will attempt to provide more metadata.

    Args:
        component_type: Type of components to list ('rule_groups', 'llm_models', 'prompts', or 'all').
        include_details: Whether to include detailed descriptions and metadata for each component.

    Returns:
        A dictionary containing 'rule_groups', 'llm_models', 'prompts', and/or 'llm_prompt_mappings'
        based on component_type.
    """
    log.info(f"Received request to list Dingo components. Type: {component_type}, Details: {include_details}")
    try:
        Model.load_model()  # Ensure all modules are loaded and components registered

        result = {}

        # Get rule groups information
        if component_type == 'rule_groups' or component_type == 'all':
            rule_info = _get_rule_groups_info(include_details)
            result.update(rule_info)

        # Get LLM models information
        if component_type == 'llm_models' or component_type == 'all':
            llm_info = _get_llm_models_info(include_details)
            result.update(llm_info)

        # Get prompts information
        if component_type == 'prompts' or component_type == 'all':
            prompts_info = _get_prompts_info(include_details)
            result.update(prompts_info)

        return result
    except Exception as e:
        log.error(f"Failed to list Dingo components: {e}", exc_info=True)
        raise RuntimeError(f"Failed to list Dingo components: {e}") from e


@mcp.tool()
def get_rule_details(rule_name: str) -> Dict:
    """Get detailed information about a specific Dingo rule.

    Retrieves information including the rule's description, parameters,
    and evaluation characteristics.

    Args:
        rule_name: The name of the rule to get details for.

    Returns:
        A dictionary containing details about the rule.
    """
    log.info(f"Received request for rule details: {rule_name}")
    try:
        Model.load_model()
        rule_groups = Model.get_rule_groups()

        if rule_name in rule_groups:
            rule_group = rule_groups[rule_name]

            # Extract basic info
            details = {'name': rule_name, 'rule_count': len(rule_group.rules), 'rules': []}

            # Get information about each rule in the group
            for rule in rule_group.rules:
                rule_info = {
                    'id': rule.rule_id,
                    'description': rule.description,
                    'category': rule.category if hasattr(rule, 'category') else 'Unknown',
                }
                details['rules'].append(rule_info)

            return details
        else:
            return {'error': f"Rule '{rule_name}' not found."}
    except Exception as e:
        log.error(f"Error retrieving rule details: {e}", exc_info=True)
        return {'error': f"Failed to retrieve rule details: {str(e)}"}


@mcp.tool()
def get_llm_details(llm_name: str) -> Dict:
    """Get detailed information about a specific Dingo LLM.

    Retrieves information including the LLM's description, capabilities,
    and configuration parameters.

    Args:
        llm_name: The name of the LLM to get details for.

    Returns:
        A dictionary containing details about the LLM.
    """
    log.info(f"Received request for LLM details: {llm_name}")
    try:
        Model.load_model()
        llm_map = Model.get_llm_name_map()

        if llm_name in llm_map:
            llm_class = llm_map[llm_name]

            # Extract basic info
            details = {'name': llm_name, 'class': llm_class.__name__, 'parameters': {}}

            # Get parameter info if available
            if hasattr(llm_class, 'MODEL_PARAMETERS'):
                details['parameters'] = llm_class.MODEL_PARAMETERS

            # Get provider info if available
            if hasattr(llm_class, 'PROVIDER'):
                details['provider'] = llm_class.PROVIDER

            # Get description if available
            if hasattr(llm_class, 'DESCRIPTION'):
                details['description'] = llm_class.DESCRIPTION
            else:
                details['description'] = f"LLM model for {llm_name}"

            return details
        else:
            return {'error': f"LLM '{llm_name}' not found."}
    except Exception as e:
        log.error(f"Error retrieving LLM details: {e}", exc_info=True)
        return {'error': f"Failed to retrieve LLM details: {str(e)}"}


@mcp.tool()
def get_prompt_details(prompt_name: str) -> Dict:
    """Get detailed information about a specific Dingo prompt.

    Retrieves information including the prompt's description, associated metric type,
    and which groups it belongs to.

    Args:
        prompt_name: The name of the prompt to get details for.

    Returns:
        A dictionary containing details about the prompt.
    """
    log.info(f"Received request for prompt details: {prompt_name}")
    try:
        Model.load_model()

        if prompt_name in Model.prompt_name_map:
            prompt_class = Model.prompt_name_map[prompt_name]

            # Extract basic info
            details = {
                'name': prompt_name,
                'content_preview': (
                    getattr(prompt_class, 'content', '')[:PROMPT_PREVIEW_MAX_LENGTH] + '...'
                    if hasattr(prompt_class, 'content')
                    else ''
                ),
            }

            # Get metric type info if available
            if hasattr(prompt_class, 'metric_type'):
                details['metric_type'] = prompt_class.metric_type

            # Get group info if available
            if hasattr(prompt_class, 'group'):
                details['groups'] = prompt_class.group

            # Find which LLMs use this prompt
            associated_llms = []
            for llm_name, llm_class in Model.llm_name_map.items():
                if hasattr(llm_class, 'prompt') and llm_class.prompt and llm_class.prompt.__name__ == prompt_name:
                    associated_llms.append(llm_name)

            if associated_llms:
                details['used_by_llms'] = associated_llms

            return details
        else:
            return {'error': f"Prompt '{prompt_name}' not found."}
    except Exception as e:
        log.error(f"Error retrieving prompt details: {e}", exc_info=True)
        return {'error': f"Failed to retrieve prompt details: {str(e)}"}


@mcp.tool()
def run_quick_evaluation(input_path: str, evaluation_goal: str) -> str:
    """Run a simplified Dingo evaluation based on a high-level goal.

    Automatically infers the appropriate evaluation type and settings
    based on the evaluation goal description.

    Args:
        input_path: Path to the file to evaluate.
        evaluation_goal: Description of what to evaluate (e.g., 'check for inappropriate content',
                         'evaluate text quality', 'assess helpfulness').

    Returns:
        A summary of the evaluation results or a path to the detailed results.
    """
    log.info(f"Received request for quick evaluation. Input: {input_path}, Goal: {evaluation_goal}")

    # Default settings
    evaluation_type = 'rule'
    eval_group_name = 'default'

    # Analyze evaluation goal to determine appropriate settings
    goal_lower = evaluation_goal.lower()

    # Define keyword mappings for evaluations
    llm_models = {
        'gpt': 'LLMTextQualityModelBase',
        'openai': 'LLMTextQualityModelBase',
        'claude': 'LLMTextQualityModelBase',
        'anthropic': 'LLMTextQualityModelBase',
        'llama': 'LLMTextQualityModelBase',
    }

    llm_features = {
        'quality': 'LLMTextQualityModelBase',
        'text quality': 'LLMTextQualityModelBase',
        'security': 'LLMSecurityProhibition',
        'safety': 'LLMSecurityProhibition',
        'inappropriate': 'LLMSecurityProhibition',
        'helpful': 'LLMText3HHelpful',
        'harmless': 'LLMText3HHarmless',
        'honest': 'LLMText3HHonest',
    }

    # Check for LLM-related keywords
    llm_detected = False
    for keyword in ['llm', 'ai', 'model', 'language model'] + list(llm_models.keys()):
        if keyword in goal_lower:
            evaluation_type = 'llm'
            llm_detected = True
            # Try to detect specific LLM model
            for model_keyword, model_name in llm_models.items():
                if model_keyword in goal_lower:
                    eval_group_name = model_name
                    break
            break

    # Check for specific evaluation features
    for feature, feature_model in llm_features.items():
        if feature in goal_lower:
            # Only switch to LLM evaluation type if not already detected as LLM
            if feature in ['helpful', 'harmless', 'honest'] or llm_detected:
                evaluation_type = 'llm'
                eval_group_name = feature_model
                break

    log.info(f"Inferred evaluation type: {evaluation_type}, group: {eval_group_name}")

    # Prepare custom settings
    kwargs_for_eval = {
        'output_dir': os.path.join(DEFAULT_OUTPUT_DIR or '.', 'quick_evals') if DEFAULT_OUTPUT_DIR else None,
        'save_data': True,
        'task_name': f"quick_{evaluation_type}_{eval_group_name}_{uuid.uuid4().hex[:6]}",
    }

    # Run the evaluation with inferred settings
    return run_dingo_evaluation(
        input_path=input_path, evaluation_type=evaluation_type, eval_group_name=eval_group_name, kwargs=kwargs_for_eval
    )


def get_prompt_for_llm(llm_name: str) -> Optional[str]:
    """Find the associated prompt name for a given LLM.

    Args:
        llm_name: The name of the LLM to look up.

    Returns:
        Associated prompt name if found, otherwise None.
    """
    log.info(f"Looking for prompt associated with LLM: '{llm_name}'")
    try:
        Model.load_model()  # Ensure models are loaded

        # Check if the llm_name is actually a prompt name
        if llm_name in Model.prompt_name_map:
            log.info(f"'{llm_name}' is already a valid prompt name")
            return llm_name

        # Check if it's a valid LLM
        if llm_name in Model.llm_name_map:
            llm_class = Model.llm_name_map[llm_name]

            # Strategy 1: Most LLM classes have a 'prompt' class attribute pointing to their default prompt
            if hasattr(llm_class, 'prompt') and llm_class.prompt:
                prompt_class = llm_class.prompt
                prompt_name = prompt_class.__name__
                log.info(f"Found associated prompt '{prompt_name}' for LLM '{llm_name}' via prompt attribute")
                return prompt_name

            # Strategy 2: Try to derive prompt name from naming patterns
            if llm_name.startswith('LLM'):
                # Strip "LLM" prefix and try with "Prompt" prefix
                base_name = llm_name[3:]  # Remove "LLM"
                potential_prompt_name = f"Prompt{base_name}"

                # Check if derived name exists
                if potential_prompt_name in Model.prompt_name_map:
                    log.info(
                        f"Found associated prompt '{potential_prompt_name}' for LLM '{llm_name}' via naming pattern"
                    )
                    return potential_prompt_name

                # Strategy 3: Try to find by suffix matching
                for prompt_name in Model.prompt_name_map:
                    if prompt_name.startswith('Prompt') and base_name.endswith(prompt_name[6:]):
                        log.info(f"Found associated prompt '{prompt_name}' for LLM '{llm_name}' via suffix matching")
                        return prompt_name

        log.warning(f"No associated prompt found for LLM '{llm_name}'")
        return None

    except Exception as e:
        log.error(f"Error finding prompt for LLM '{llm_name}': {e}", exc_info=True)
        return None


if __name__ == '__main__':
    if os.environ.get('LOCAL_DEPLOYMENT_MODE') == 'true':
        mcp.run()
    else:
        mcp.run(transport='sse')
