import "clsx";
import "./userStore.js";
import "@sveltejs/kit/internal";
import "./exports.js";
import "./utils.js";
import "@sveltejs/kit/internal/server";
import "./state.svelte.js";
import axios from "axios";
async function handleApiResponse(response) {
  return false;
}
function getAuthToken() {
  return null;
}
async function authenticatedFetch(url, options = {}) {
  const token = getAuthToken();
  if (!token) {
    throw new Error("No authentication token available");
  }
  const defaultHeaders = {
    "Authorization": `Bearer ${token}`
  };
  if (!(options.body instanceof FormData)) {
    defaultHeaders["Content-Type"] = "application/json";
  }
  const defaultOptions = {
    headers: defaultHeaders
  };
  const mergedOptions = {
    ...defaultOptions,
    ...options,
    headers: {
      ...defaultOptions.headers,
      ...options.headers || {}
    }
  };
  const response = await fetch(url, mergedOptions);
  await handleApiResponse();
  return response;
}
axios.interceptors.request.use((config) => {
  const token = getAuthToken();
  if (token) {
    config.headers.set("Authorization", `Bearer ${token}`);
  }
  return config;
});
axios.interceptors.response.use(
  (response) => response,
  async (error) => {
    if (error.response) {
      ({
        status: error.response.status
      });
      await handleApiResponse();
    }
    return Promise.reject(error);
  }
);
export {
  authenticatedFetch as a
};
