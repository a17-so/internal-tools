function doPost(e) {
  try {
    const data = JSON.parse(e.postData.contents);
    const profileUrl = data.profileUrl;
    const category = data.category; // "Macro", "Micro", "Ambassador"

    const ss = SpreadsheetApp.getActiveSpreadsheet();
    const sheet = ss.getSheetByName("Creators");

    // ----- 1. Pick outreach script -----
    const { emailScript, dmScript } = getScripts(category);

    // ----- 2. Scrape profile -----
    const profile = scrapeProfile(profileUrl);

    // ----- 3. Add to Sheet -----
    const totalFollowers = (profile.igFollowers || 0) + (profile.ttFollowers || 0) + (profile.ytFollowers || 0);

    const newRow = [
      profile.name || "",
      profile.ig || "",
      profile.tt || "",
      profile.yt || "",
      profile.igFollowers || "",
      profile.ttFollowers || "",
      profile.ytFollowers || "",
      totalFollowers,
      profile.email || "",
      "Pending"
    ];
    sheet.appendRow(newRow);

    // ----- 4. Send Email -----
    let emailStatus = "No email found";
    if (profile.email) {
      GmailApp.sendEmail(
        profile.email,
        "Paid Partnership Opportunity with Pretti",
        emailScript.replace("[Name]", profile.name || "there")
      );
      emailStatus = "Email sent";
    }

    // ----- 5. Return JSON for Shortcut -----
    const response = {
      igLink: profile.ig ? "https://instagram.com/" + profile.ig : "IG not there",
      dmScript: dmScript.replace("[Name]", profile.name || "there"),
      emailStatus: emailStatus
    };
    return ContentService.createTextOutput(JSON.stringify(response))
      .setMimeType(ContentService.MimeType.JSON);

  } catch (err) {
    return ContentService.createTextOutput(JSON.stringify({ error: err.message }))
      .setMimeType(ContentService.MimeType.JSON);
  }
}


// --- Hardcoded outreach scripts ---
function getScripts(category) {
  const scripts = {
    "Macro": {
      emailScript: "Hey [Name], we love your content! We'd like to partner with you for Pretti App. Let’s chat!",
      dmScript: "Hi [Name], big fan of your content! We’d love to invite you to collaborate with Pretti 💄"
    },
    "Micro": {
      emailScript: "Hey [Name], your style really fits our brand. We'd love to feature you as a Pretti partner!",
      dmScript: "Hi [Name], love your content! Would you be open to a collab with Pretti?"
    },
    "Ambassador": {
      emailScript: "Hey [Name], we’re launching an ambassador program for Pretti and think you’d be perfect!",
      dmScript: "Hi [Name], we're starting an ambassador program for Pretti. Would love for you to join 💕"
    }
  };
  return scripts[category] || scripts["Micro"];
}


// --- Scrape TikTok/IG Profile ---
function scrapeProfile(url) {
  let details = { name: "", email: "", ig: "", tt: "", yt: "", igFollowers: 0, ttFollowers: 0, ytFollowers: 0 };

  try {
    const html = UrlFetchApp.fetch(url, { muteHttpExceptions: true }).getContentText();

    // Extract name from <title>
    const nameMatch = html.match(/<title>(.*?)<\/title>/);
    details.name = nameMatch ? nameMatch[1].replace(/[\n\r]/g, '').trim() : "";

    // Extract email
    const emailMatch = html.match(/[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-z]{2,}/);
    details.email = emailMatch ? emailMatch[0] : "";

    // Extract IG/TikTok mentions (bio link style)
    const igMatch = html.match(/(?:ig|IG|instagram|Instagram)[: ]+([a-zA-Z0-9_.]+)/);
    if (igMatch) details.ig = igMatch[1];

    const ttMatch = html.match(/(?:tt|TT|tiktok|TikTok)[: ]+([a-zA-Z0-9_.]+)/);
    if (ttMatch) details.tt = ttMatch[1];

    // Extract Instagram URL form
    const igUrlMatch = html.match(/instagram\.com\/([a-zA-Z0-9_.]+)/);
    if (igUrlMatch && !details.ig) details.ig = igUrlMatch[1];

    // Extract TikTok username form
    const ttUrlMatch = html.match(/tiktok\.com\/@([a-zA-Z0-9_.]+)/);
    if (ttUrlMatch && !details.tt) details.tt = ttUrlMatch[1];

    // Extract YouTube username form
    const ytUrlMatch = html.match(/youtube\.com\/(c|channel|@)([a-zA-Z0-9_.-]+)/);
    if (ytUrlMatch) details.yt = ytUrlMatch[2];

    // Followers count (very heuristic, depends on platform HTML)
    const followerMatch = html.match(/([0-9,.]+)\s?(Followers|followers|Follower)/g);
    if (followerMatch) {
      // crude: assign first match to TikTok
      details.ttFollowers = parseFollowers(followerMatch[0]);
    }

  } catch (err) {
    Logger.log("Scrape failed: " + err);
  }

  return details;
}


// --- Helper: normalize follower counts ---
function parseFollowers(str) {
  if (!str) return 0;
  str = str.toLowerCase().replace(/followers?/, "").trim();

  if (str.includes("k")) return Math.round(parseFloat(str) * 1000);
  if (str.includes("m")) return Math.round(parseFloat(str) * 1000000);
  return parseInt(str.replace(/,/g, "")) || 0;
}
