async function submitKnowledgeBaseCreation(page, submitButton) {
  const rateLimitRetryDelays = [15_000, 45_000];

  for (let attempt = 0; ; attempt += 1) {
    const createResponsePromise = page.waitForResponse(
      (response) => {
        const url = new URL(response.url());
        return (
          response.request().method() === "POST" &&
          url.pathname.endsWith("/creator/knowledgebases")
        );
      },
      { timeout: 30_000 },
    );

    await submitButton.click();
    const response = await createResponsePromise;

    if (response.ok()) {
      return response;
    }

    const responseBody = await response.text().catch(() => "<unreadable body>");
    const isRateLimited =
      response.status() === 429 ||
      /rate limit exceeded|RateLimitError/i.test(responseBody);
    const retryDelay = rateLimitRetryDelays[attempt];

    if (isRateLimited && retryDelay !== undefined) {
      console.warn(
        `Knowledge base creation was rate-limited; retrying in ${retryDelay / 1000}s`,
      );
      await page.waitForTimeout(retryDelay);
      await submitButton.waitFor({ state: "visible" });
      continue;
    }

    throw new Error(
      `Knowledge base creation failed: HTTP ${response.status()} ${response.statusText()}\n${responseBody}`,
    );
  }
}

module.exports = { submitKnowledgeBaseCreation };
