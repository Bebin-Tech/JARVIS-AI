export const companionMessage =
  "Desktop companion unavailable. Open JARVIS on this PC at http://127.0.0.1:8000 to use AI, voice and Windows controls.";

export async function readApiJson(response: Response) {
  const type = response.headers.get("content-type")?.toLowerCase() ?? "";
  if (!type.includes("application/json") && !type.includes("+json")) {
    throw new Error(companionMessage);
  }
  try {
    return await response.json();
  } catch {
    throw new Error(
      "The backend returned an invalid response. Please restart the JARVIS desktop companion and try again.",
    );
  }
}
