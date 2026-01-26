# evaluations/evaluate_assistant.py
import os
import requests
import re
from pathlib import Path
from typing import Dict, Any, Union
from dotenv import load_dotenv
from langsmith import evaluate, Client, wrappers
from langsmith.schemas import Run, Example
from openai import OpenAI

# Load environment variables from backend
project_root = Path(__file__).parent.parent.parent
load_dotenv(project_root / "backend" / ".env")

# Configuration
API_BASE_URL = "http://localhost:9099"
JWT_TOKEN = "your_jwt_token_here"  # Replace with your actual JWT token
ASSISTANT_ID = 1  # Replace with your actual assistant ID
DATASET_NAME = "dbizi dataset"

# Initialize OpenAI client for the evaluator
openai_client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))

def chat_with_assistant(
    token: str,
    assistant_id: int,
    message: str,
    stream: bool = False,
    base_url: str = API_BASE_URL
) -> Union[Dict[Any, Any], requests.Response]:
    """
    Sends a message to an assistant and gets the response.
    """
    url = f"{base_url}/creator/assistant/{assistant_id}/chat/completions"

    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }

    payload = {
        "messages": [
            {
                "role": "user",
                "content": message
            }
        ],
        "stream": stream
    }

    response = requests.post(url, json=payload, headers=headers, stream=stream)
    response.raise_for_status()

    if stream:
        return response
    else:
        return response.json()


def ask_question(question: str) -> str:
    """
    Sends a question to the assistant and returns the response.
    """
    try:
        response = chat_with_assistant(
            token=JWT_TOKEN,
            assistant_id=ASSISTANT_ID,
            message=question,
            stream=False
        )
        
        # Adjust this according to your actual response format
        if isinstance(response, dict) and "choices" in response:
            return response["choices"][0]["message"]["content"]
        else:
            return str(response)
    
    except Exception as e:
        print(f"Error processing question '{question}': {e}")
        return None


def target_function(inputs: dict) -> dict:
    """
    Target function for LangSmith evaluate.
    
    Receives inputs from the dataset and returns outputs that the evaluator can use.
    """
    question = inputs["question"]
    answer = ask_question(question)
    return {"output": answer}

def similarity_score_evaluator(run: Run, example: Example) -> dict:
    """
    LLM-as-a-Judge evaluator that assesses the similarity between the 
    generated output and the reference output, given an input context.
    
    Returns a score from 1-10 where:
    - 1 is the least similar
    - 10 is almost identical
    
    Args:
        run: Contains the generated output
        example: Contains the input and the reference output (answer)
    """
    # Extract data
    input_text = example.inputs.get("question", "")
    output_text = run.outputs.get("output", "")
    reference_output = example.outputs.get("answer", "")
    
    # Build the prompt according to LangSmith structure
    system_prompt = """You are an expert at comparing two answers.
You are assessing a similarity between the reference and the submission output, given an input question as context. Similarity will have a high score if the answers are very close in meaning and low score if they are very different. Both answers may contain additional information, but focus on the core answer to the question. Both answers must be in the same language as the question."""
    
    user_prompt = f"""Please grade the following example according to the above instructions:

<example>
<input>
{input_text}
</input>

<output>
{output_text}
</output>

<reference_outputs>
{reference_output}
</reference_outputs>
</example>

IMPORTANT: Your response MUST be in the format "Grade:X",where X is a number from 1 to 10 indicating the similarity score."""
    
    try:
        # Call the LLM judge (gpt-4.1)
        response = openai_client.chat.completions.create(
            model="gpt-4.1",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            temperature=0
        )
        
        # Get the response
        judge_response = response.choices[0].message.content
        print(f"Judge response: {judge_response}")
        # Extract the numeric score in "Grade:X" format
        score_match = re.search(r'Grade:\s*(10|[1-9])', judge_response, re.IGNORECASE)
        
        if score_match:
            score = int(score_match.group(1))
        else:
            score = 0
        
    except Exception as e:
        print(f"Error in LLM evaluator: {e}")
        score = 0  # Default score in case of error
    
    return {
        "key": "similarity",
        "score": score
    }

def run_evaluation():
    """
    Runs the assistant evaluation using an LLM-as-a-judge evaluator.
    """
    print(f"🚀 Starting evaluation of assistant {ASSISTANT_ID}")
    print(f"📊 Dataset: {DATASET_NAME}")
    print(f"🌐 API URL: {API_BASE_URL}")
    
    client = Client()
    
    results = evaluate(
        target_function,
        data=DATASET_NAME,
        experiment_prefix="Dbizi test",
        evaluators=[similarity_score_evaluator],
        metadata={
            "keyword": "test",
            "assistant_id": ASSISTANT_ID,
            "base_url": API_BASE_URL,
        }
    )
    
    print("\n✅ Evaluation completed")
    print(f"📊 Review the results in LangSmith")
    return results


if __name__ == "__main__":
    run_evaluation()