# core/gemini_api.py
import google.generativeai as genai
import requests.exceptions
import time
from . import config_manager

# --- Safety Settings ---
SAFETY_SETTINGS = [
    {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_MEDIUM_AND_ABOVE"},
    {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_MEDIUM_AND_ABOVE"},
    {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_MEDIUM_AND_ABOVE"},
    {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_MEDIUM_AND_ABOVE"},
]
# --- Generation Config ---
GENERATION_CONFIG = {
    "temperature": 0.7,
    "top_p": 1.0,
    "top_k": 1,
    "max_output_tokens": 2048,
}

_genai_configured = False # Module level flag

def configure_genai():
    """Configures the genai library with the API key."""
    global _genai_configured
    api_key = config_manager.get_setting('API', 'api_key')
    if not api_key:
        print("API Key not found in configuration.")
        _genai_configured = False
        return False
    try:
        genai.configure(api_key=api_key)
        _genai_configured = True
        print("GenAI configured successfully.")
        return True
    except Exception as e:
        print(f"Error configuring GenAI: {e}")
        _genai_configured = False
        return False

def list_models():
    """Lists available Gemini models (requires API key configured)."""
    if not _genai_configured:
        if not configure_genai(): # Attempt to configure if not already done
             return ["Error: API Key not configured or invalid"]

    models_cache = []
    try:
        start_time = time.time()
        print("Fetching available models from API...")
        all_models = genai.list_models()
        print("Parsing model list...",all_models)
        # Filter for models that support 'generateContent' and start with 'gemini-'
        models_cache = sorted([m.name.replace('models/', '')
                               for m in all_models
                               if 'generateContent' in m.supported_generation_methods and m.name.startswith('models/gemini-')])
        duration = time.time() - start_time
        print(f"Model list fetched in {duration:.2f}s. Found: {models_cache}")
        return models_cache if models_cache else ["Error: No suitable Gemini models found"]
    except Exception as e:
        print(f"Error listing models from API: {e}")
        # Fallback to configured models if API fails
        configured_models_str = config_manager.get_setting('Models', 'available_models')
        fallback_models = configured_models_str.split(',') if configured_models_str else []
        print(f"Falling back to models from config: {fallback_models}")
        # Ensure fallback list isn't empty
        if not fallback_models:
            fallback_models = ["gemini-1.5-flash-latest"] # Hardcoded minimal fallback
            print(f"Using hardcoded fallback model: {fallback_models}")

        # Return fallback list, ensuring an error message if even that is empty
        return fallback_models if fallback_models else ["Error: Could not fetch models and no fallback available"]


def send_query(prompt, model_name):
    """Sends a query to the specified Gemini model."""
    global _genai_configured
    if not _genai_configured:
        if not configure_genai():
            return "Error: API Key not configured or invalid."

    try:
        print(f"Sending query to model: {model_name}")
        model = genai.GenerativeModel(model_name=model_name,
                                      generation_config=GENERATION_CONFIG,
                                      safety_settings=SAFETY_SETTINGS)

        # Simple non-chat generation
        # TODO: Implement conversational history using model.start_chat()
        response = model.generate_content(prompt)
        print("Response received from API.")

        # Enhanced response handling based on google-generativeai v0.3+ structure
        if response.parts:
             return "".join(part.text for part in response.parts) # Concatenate parts if needed

        elif response.prompt_feedback and response.prompt_feedback.block_reason:
             reason = response.prompt_feedback.block_reason.name
             print(f"Query blocked due to: {reason}")
             # Check for specific safety ratings if available
             details = []
             if response.prompt_feedback.safety_ratings:
                 for rating in response.prompt_feedback.safety_ratings:
                     details.append(f"{rating.category.name}: {rating.probability.name}")
             detail_str = f" ({', '.join(details)})" if details else ""
             return f"Error: Content blocked by API due to {reason}{detail_str}. Please modify your prompt."

        elif response.candidates and response.candidates[0].finish_reason != genai.types.FinishReason.STOP:
             # Handle other finish reasons like MAX_TOKENS, SAFETY, RECITATION, OTHER
             reason = response.candidates[0].finish_reason.name
             print(f"Generation finished abnormally: {reason}")
             if reason == 'MAX_TOKENS':
                 return response.text + "\n[... Output truncated due to length limit ...]"
             else:
                 # Provide more context if available (e.g., safety ratings for the candidate)
                 safety_details = []
                 if response.candidates[0].safety_ratings:
                    for rating in response.candidates[0].safety_ratings:
                         safety_details.append(f"{rating.category.name}: {rating.probability.name}")
                 detail_str = f" ({', '.join(safety_details)})" if safety_details else ""
                 return f"Error: Response generation stopped due to {reason}{detail_str}."

        else:
             # Catch-all for unexpected empty responses
             print("Warning: Received empty response from API without explicit blocking or abnormal finish reason.")
             return "Error: Received an empty or unexpected response from the API."


    except requests.exceptions.RequestException as e:
        print(f"Network error connecting to Gemini API: {e}")
        return f"Network Error: Could not connect to API. Check your internet connection. Details: {e}"
    except google.api_core.exceptions.PermissionDenied as e:
         print(f"Permission Denied Error (likely API Key issue): {e}")
         # Attempt to reset configured state so next attempt re-validates
         
         _genai_configured = False
         return "Error: Invalid API Key or insufficient permissions. Please check settings. Details: API key not valid." # More direct message
    except google.api_core.exceptions.ResourceExhausted as e:
         print(f"Resource Exhausted Error (likely Quota): {e}")
         return "Error: API Quota Exceeded. Please check your usage limits or wait and try again."
    except Exception as e:
        # Catch other potential GenAI errors or unexpected issues
        print(f"An unexpected error occurred interacting with Gemini API: {e}")
        error_type = type(e).__name__
        # Try to provide a slightly more informative generic error
        return f"API Error: An unexpected error occurred ({error_type}). Check logs for details. Message: {e}"

# Attempt initial configuration when module is loaded
# configure_genai() # Calling this here might print errors if key isn't set yet. Better to call on demand.

