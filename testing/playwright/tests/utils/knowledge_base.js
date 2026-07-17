async function submitKnowledgeBaseCreation(page, submitButton) {
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

  if (!response.ok()) {
    const responseBody = await response.text().catch(() => "<unreadable body>");
    throw new Error(
      `Knowledge base creation failed: HTTP ${response.status()} ${response.statusText()}\n${responseBody}`,
    );
  }

  return response;
}

module.exports = { submitKnowledgeBaseCreation };
