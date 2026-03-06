import { g as getApiUrl } from "./config.js";
async function fetchUserProfile(token) {
  try {
    const response = await fetch(getApiUrl("/me"), {
      method: "GET",
      headers: {
        "Authorization": `Bearer ${token}`
      }
    });
    let data;
    try {
      const text = await response.text();
      data = text ? JSON.parse(text) : {};
    } catch (e) {
      console.error("Failed to parse profile response:", e);
      data = {};
    }
    if (!response.ok) {
      throw new Error(data?.error || "Failed to fetch user profile");
    }
    return data;
  } catch (error) {
    console.error("Fetch user profile error:", error);
    let message = "An error occurred while fetching user profile";
    if (error instanceof Error) {
      message = error.message;
    }
    return {
      success: false,
      error: message
    };
  }
}
export {
  fetchUserProfile
};
