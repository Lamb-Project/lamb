import OpenAI from 'openai';
import { json } from '@sveltejs/kit';

/**
 * @param {import('@sveltejs/kit').RequestEvent} event
 */
export async function POST(event) {
  try {
    // Extract data from the request
    const requestData = await event.request.json();
    const { messages, apiUrl, apiKey } = requestData;

    if (!apiUrl || !apiKey) {
      return json(
        { error: 'API URL and API Key are required' },
        { status: 400 }
      );
    }

    // Create a custom OpenAI client with the provided credentials
    const openai = new OpenAI({
      apiKey,
      baseURL: apiUrl
    });

    // Use a simple model name - the server will choose a suitable one
    const modelName = 'gpt-3.5-turbo';

    // Get the response stream
    const response = await openai.chat.completions.create({
      model: modelName, 
      messages,
      stream: true
    });

    // Create a simple streaming response
    const stream = new ReadableStream({
      async start(controller) {
        const encoder = new TextEncoder();
        
        try {
          for await (const chunk of response) {
            const content = chunk.choices[0]?.delta?.content || '';
            if (content) {
              controller.enqueue(encoder.encode(content));
            }
          }
          controller.close();
        } catch (error) {
          console.error('Stream error:', error);
          controller.error(error);
        }
      }
    });

    // Return a streaming response
    return new Response(stream, {
      headers: {
        'Content-Type': 'text/plain; charset=utf-8'
      }
    });
  } catch (error) {
    console.error('Error in chat API:', error);
    return json(
      { error: error instanceof Error ? error.message : 'An unknown error occurred' },
      { status: 500 }
    );
  }
} 