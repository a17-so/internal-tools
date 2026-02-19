const API_BASE =
    "https://outreach-tool-api-544313478134.us-central1.run.app";

/* ─── Types ─── */

export interface ScrapeRequest {
    app: string;
    category: string;
    creator_url: string;
    sender_profile?: string;
    include_extras?: boolean;
}

export interface ScrapeResponse {
    message?: string;
    dm_message?: string;
    email_subject?: string;
    email_body?: string;
    creator_name?: string;
    creator_email?: string;
    creator_ig?: string;
    sheet_row_added?: boolean;
    error?: string;
    [key: string]: unknown;
}

export interface AppConfig {
    [appName: string]: {
        spreadsheet_id: string;
        sender_profiles?: Record<string, unknown>;
        [key: string]: unknown;
    };
}

/* ─── Endpoints ─── */

export async function fetchApps(): Promise<Record<string, any>> {
    const res = await fetch(`${API_BASE}/debug/config`);
    const data = await res.json();
    // The API wraps configs in an "app_configs" key
    const configs = data.app_configs || data;
    return configs;
}

export async function validateApp(
    app: string,
    senderProfile?: string
): Promise<Record<string, unknown>> {
    const res = await fetch(`${API_BASE}/validate`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
            app,
            ...(senderProfile ? { sender_profile: senderProfile } : {}),
        }),
    });
    return res.json();
}

export async function submitScrape(
    req: ScrapeRequest
): Promise<ScrapeResponse> {
    const payload = {
        ...req,
        tiktok_url: req.creator_url,
        include_extras: true
    };

    const endpoint =
        req.category.toLowerCase() === "themepage"
            ? "/scrape_themepage"
            : "/scrape";

    const res = await fetch(`${API_BASE}${endpoint}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
    });

    const data = await res.json();

    if (!res.ok) {
        throw new Error(data.error || data.message || `HTTP ${res.status}`);
    }

    return data;
}

export async function updateCreatorContact(payload: {
    app: string;
    ig_handle?: string;   // scraped ig — for row lookup
    tt_handle?: string;   // scraped tt — for row lookup
    new_email?: string;   // override to write to sheet col D
    new_ig?: string;      // override to write to sheet col B
}): Promise<{ ok: boolean; updated?: string[]; error?: string }> {
    const res = await fetch(`${API_BASE}/update_creator_contact`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
    });
    return res.json();
}
