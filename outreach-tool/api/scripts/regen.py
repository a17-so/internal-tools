def get_templates(app_name="REGEN", app_config=None):
    """Generate templates dynamically based on app configuration."""
    if app_config is None:
        app_config = {}

    # Extract app-specific information from config
    app_display_name = app_config.get("from_name", "Abhay Chebium")
    app_site = app_config.get("site_url", "regenhealth.app")

    # Common sections
    INTRO = (
        f"{app_name.upper()} is a peptide transformation app that uses AI to help you with your peptide cycle.\n\n"
    )

    IMAGE_LINK = (
        "here are some images of the product:\n"
        "https://drive.google.com/drive/u/0/folders/1JWJ4bfA1a55G6Ifp4Trw7WZCXENPo7pu\n\n"
    )

    UGC_DELIVERABLES_FORM = (
        "here is a brief about deliverables + rate:\n"
        "https://regenhealth.app/ugc\n\n"
    )

    THEMEPAGE_DELIVERABLES_LINK = (
        "here is a brief about deliverables + rate: "
        "https://www.notion.so/REGEN-Clipping-Program-2c739b5e840f800e826bc1cc0569aea3\n\n"
    )

    YT_DELIVERABLES_LINK = (
        "here is a brief about deliverables + rate: "
        "https://www.notion.so/REGEN-YT-Creator-Program-31539b5e840f8002b6e5ceeb6dab0d83\n\n"
    )

    AI_INFLUENCER_DELIVERABLES_LINK = (
        "here is a brief about deliverables + rate: "
        "https://www.regenhealth.app/ai-influencers\n\n"
    )

    # Variant specific texts
    MACRO_TEXT = "we're inviting a few, bigtime health/fitness/beauty creators who have a cultlike following to try it out & pay you to promote the app.\n\n"
    MICRO_TEXT = "we're inviting a few, niche health/fitness/beauty creators who have a cultlike following to try it out & pay you to promote the app.\n\n"
    AMBASSADOR_TEXT = "we're inviting people to create new socials and promote our app.\n\n"
    YT_CREATOR_TEXT = "we're inviting a few, talented YT creators who have a cultlike following to try it out & pay you to promote the app.\n\n"
    AI_INFLUENCER_TEXT = "we'd love to pay you to promote our app. we have 10+ AI accounts posting for us.\n\n"
    THEMEPAGE_TEXT = "we'd love to pay you to promote our app. we have 10+ themepages posting for us.\n\n"

    def build_body(
        variant_text,
        email=False,
        include_images=False,
        deliverables_mode=None,
    ):
        body = f"hey {{name}},\n\npaid promo?\n\n{INTRO}{variant_text}"

        if email and include_images:
            body += IMAGE_LINK

        if email:
            if deliverables_mode == "bullets":
                body += UGC_DELIVERABLES_FORM
            elif deliverables_mode == "themepage_link":
                body += THEMEPAGE_DELIVERABLES_LINK
            elif deliverables_mode == "yt_link":
                body += YT_DELIVERABLES_LINK
            elif deliverables_mode == "ai_link":
                body += AI_INFLUENCER_DELIVERABLES_LINK

        body += "let me know if you're interested.\n\n"

        signoff = f"- {app_display_name} from the {app_name.upper()} App"
        if email:
            signoff += f" ({app_site})"

        return body + signoff + "\n"

    return {
        "macro": {
            "subject": f"PAID PROMO OPPORTUNITY - {app_name.upper()} App",
            "email_md": build_body(
                MACRO_TEXT,
                email=True,
                include_images=False,
                deliverables_mode=None,
            ),
            "dm_md": build_body(
                MACRO_TEXT,
                email=False,
                include_images=False,
                deliverables_mode=None,
            ),
        },
        "micro": {
            "subject": f"PAID PROMO OPPORTUNITY - {app_name.upper()} App",
            "email_md": build_body(
                MICRO_TEXT,
                email=True,
                include_images=True,
                deliverables_mode="bullets",
            ),
            "dm_md": build_body(
                MICRO_TEXT,
                email=False,
                include_images=False,
                deliverables_mode=None,
            ),
        },
        "submicro": {
            "subject": f"PAID PROMO OPPORTUNITY - {app_name.upper()} App",
            "email_md": build_body(
                MICRO_TEXT,
                email=True,
                include_images=True,
                deliverables_mode="bullets",
            ),
            "dm_md": build_body(
                MICRO_TEXT,
                email=False,
                include_images=False,
                deliverables_mode=None,
            ),
        },
        "ambassador": {
            "subject": f"PAID PROMO OPPORTUNITY - {app_name.upper()} App",
            "email_md": build_body(
                AMBASSADOR_TEXT,
                email=True,
                include_images=True,
                deliverables_mode="bullets",
            ),
            "dm_md": build_body(
                AMBASSADOR_TEXT,
                email=False,
                include_images=False,
                deliverables_mode=None,
            ),
        },
        "themepage": {
            "subject": f"PAID PROMO OPPORTUNITY - {app_name.upper()} App",
            "email_md": build_body(
                THEMEPAGE_TEXT,
                email=True,
                include_images=False,
                deliverables_mode="themepage_link",
            ),
            "dm_md": build_body(
                THEMEPAGE_TEXT,
                email=False,
                include_images=False,
                deliverables_mode=None,
            ),
        },
        "yt_creator": {
            "subject": f"PAID PROMO OPPORTUNITY - {app_name.upper()} App",
            "email_md": build_body(
                YT_CREATOR_TEXT,
                email=True,
                include_images=True,
                deliverables_mode="yt_link",
            ),
            "dm_md": build_body(
                YT_CREATOR_TEXT,
                email=False,
                include_images=False,
                deliverables_mode=None,
            ),
        },
        "ai_influencer": {
            "subject": f"PAID PROMO OPPORTUNITY - {app_name.upper()} App",
            "email_md": build_body(
                AI_INFLUENCER_TEXT,
                email=True,
                include_images=True,
                deliverables_mode="ai_link",
            ),
            "dm_md": build_body(
                AI_INFLUENCER_TEXT,
                email=False,
                include_images=False,
                deliverables_mode=None,
            ),
        },
    }


# Legacy compatibility - create static templates for backward compatibility
TEMPLATES = get_templates()