import OpenAI from "openai";
import { json } from "@sveltejs/kit";
async function POST(event) {
  try {
    const requestData = await event.request.json();
    const { messages, apiUrl, apiKey } = requestData;
    if (!apiUrl || !apiKey) {
      return json(
        { error: "API URL and API Key are required" },
        { status: 400 }
      );
    }
    const openai = new OpenAI({
      apiKey,
      baseURL: apiUrl
    });
    const modelName = "gpt-3.5-turbo";
    const response = await openai.chat.completions.create({
      model: modelName,
      messages,
      stream: true
    });
    const stream = new ReadableStream({
      async start(controller) {
        const encoder = new TextEncoder();
        try {
          for await (const chunk of response) {
            const content = chunk.choices[0]?.delta?.content || "";
            if (content) {
              controller.enqueue(encoder.encode(content));
            }
          }
          controller.close();
        } catch (error) {
          console.error("Stream error:", error);
          controller.error(error);
        }
      }
    });
    return new Response(stream, {
      headers: {
        "Content-Type": "text/plain; charset=utf-8"
      }
    });
  } catch (error) {
    console.error("Error in chat API:", error);
    return json(
      { error: error instanceof Error ? error.message : "An unknown error occurred" },
      { status: 500 }
    );
  }
}
export {
  POST
};
