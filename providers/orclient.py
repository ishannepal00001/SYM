from openrouter import OpenRouter, close_clients


class ORClient:
    def __init__(self, api_key) -> None:
        self.client = OpenRouter(api_key=api_key)

    def stream_chat(self):
        try:
            response = self.client.chat.send(
                model="~openai/gpt-latest",
                messages=[{"role": "user", "content": "What is the meaning of life?"}],
                stream=True,
                max_completion_tokens=2048,
                top_p=1,
                reasoning_effort="medium",
                stop=None,
                temperature=1,
            )
            print(response)
        finally:
            self.client.__exit__(None, None, None)

    def chat(self, message: str):
        response = self.client.chat.send(
            model="~deepseek/deepseek-v4-flash-latest",
            messages=[{"role": "user", "content": str(message)}],
            max_completion_tokens=2048,
            top_p=1,
            reasoning_effort="medium",
            stop=None,
            temperature=1,
        )
        print(response.choices[0].message.content)
        return response.choices[0].message.content
