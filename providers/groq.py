from groq import Groq


class GroqClient:
    def __init__(self, api_key) -> None:
        self.client = Groq(api_key=api_key)

    def stream_chat(self):
        completion = self.client.chat.completions.create(
            model="openai/gpt-oss-120b",
            messages=[{"role": "user", "content": "Wake Up daddy's home!"}],
            temperature=1,
            max_completion_tokens=2048,
            top_p=1,
            reasoning_effort="medium",
            stream=True,
            stop=None,
        )

        for chunk in completion:
            print(chunk.choices[0].delta.content or "", end="")

    def chat(self, message):
        completion = self.client.chat.completions.create(
            model="openai/gpt-oss-120b",
            messages=[{"role": "user", "content": str(message)}],
            temperature=1,
            max_completion_tokens=2048,
            top_p=1,
            reasoning_effort="medium",
            stop=None,
        )
        return completion.choices[0].message.content
