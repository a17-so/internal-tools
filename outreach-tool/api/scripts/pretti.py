def get_templates(app_name="pretti", app_config=None):
    """Generate templates dynamically based on app configuration."""
    if app_config is None:
        app_config = {}
    
    # Extract app-specific information from config
    app_display_name = app_config.get("from_name", "Abhay Chebium")
    app_url = app_config.get("link_url", "https://a17.so")
    tiktok_account = app_config.get("tiktok_account", "@app.pretti")
    instagram_account = app_config.get("instagram_account", "@abhaychebium")
    
    return {
        "macro": {
            "subject": f"PAID PROMO OPPORTUNITY - {app_name.title()} App",
            "email_md": (
                "hey {name},\n\n"
                "paid promo?\n\n"
                f"{app_name.title()} is an AI beauty app that gives you step-by-step guides to recreate any makeup look and helps you shop for the right products that match your style and skin.\n\n"
                "we're inviting a few, **bigtime beauty creators** who have a **cultlike following** to try it out & pay you to promote the app :)\n\n"
                "Let me know if you're interested!\n\n"
                f"-**{app_display_name}** from the [{app_name.title()} App]({app_url})\n"
            ),
            "dm_md": (
                "hey {name},\n\n"
                "paid promo?\n\n"
                f"{app_name.title()} is an AI beauty app that gives you step-by-step guides to recreate any makeup look and helps you shop for the right products that match your style and skin.\n\n"
                "we're inviting a few, bigtime beauty creators who have a cultlike following to try it out & pay you to promote the app :)\n\n"
                "Let me know if you're interested!\n\n"
                f"-{app_display_name} from the {app_name.title()} App\n"
            ),
        },
        "micro": {
            "subject": f"PAID PROMO OPPORTUNITY - {app_name.title()} App",
            "email_md": (
                "hey {name},\n\n"
                "paid promo?\n\n"
                f"{app_name.title()} is an AI beauty app that gives you step-by-step guides to recreate any makeup look and helps you shop for the right products that match your style and skin.\n\n"
                "we're inviting a few, **niche beauty creators** who have a lot of **talent** to try it out & pay you to promote the app :)\n\n"
                "Let me know if you're interested!\n\n"
                f"-**{app_display_name}** from the [{app_name.title()} App]({app_url})\n"
            ),
            "dm_md": (
                "hey {name},\n\n"
                "paid promo?\n\n"
                f"{app_name.title()} is an AI beauty app that gives you step-by-step guides to recreate any makeup look and helps you shop for the right products that match your style and skin.\n\n"
                "we're inviting a few, niche beauty creators who have a lot of talent to try it out & pay you to promote the app :)\n\n"
                "Let me know if you're interested!\n\n"
                f"-{app_display_name} from the {app_name.title()} App\n"
            ),
        },
        "submicro": {
            "subject": f"PAID PROMO OPPORTUNITY - {app_name.title()} App",
            "email_md": (
                "hey {name},\n\n"
                "paid promo?\n\n"
                f"{app_name.title()} is an AI beauty app that gives you step-by-step guides to recreate any makeup look and helps you shop for the right products that match your style and skin.\n\n"
                "we're inviting a few, **niche beauty creators** who have a lot of **talent** to try it out & pay you to promote the app :)\n\n"
                "Let me know if you're interested!\n\n"
                f"-**{app_display_name}** from the [{app_name.title()} App]({app_url})\n"
            ),
            "dm_md": (
                "hey {name},\n\n"
                "paid promo?\n\n"
                f"{app_name.title()} is an AI beauty app that gives you step-by-step guides to recreate any makeup look and helps you shop for the right products that match your style and skin.\n\n"
                "we're inviting a few, niche beauty creators who have a lot of talent to try it out & pay you to promote the app :)\n\n"
                "Let me know if you're interested!\n\n"
                f"-{app_display_name} from the {app_name.title()} App\n"
            ),
        },
        "ambassador": {
            "subject": f"PAID PROMO OPPORTUNITY - {app_name.title()} App",
            "email_md": (
                "hey {name},\n\n"
                "paid promo?\n\n"
                f"{app_name.title()} is an AI beauty app that gives you step-by-step guides to recreate any makeup look and helps you shop for the right products that match your style and skin.\n\n"
                "we're looking for creators with **great energy** to make brand new tiktok accounts and post 15 videos per week for $400. I think you'd be a great fit for it! would you be interested?\n\n"
                "Let me know if you're interested!\n\n"
                f"-**{app_display_name}** from the [{app_name.title()} App]({app_url})\n"
            ),
            "dm_md": (
                "hey {name},\n\n"
                "paid promo?\n\n"
                f"{app_name.title()} is an AI beauty app that gives you step-by-step guides to recreate any makeup look and helps you shop for the right products that match your style and skin.\n\n"
                "we're looking for creators with great energy to make brand new tiktok accounts and post 15 videos per week for $400. I think you'd be a great fit for it! would you be interested?\n\n"
                "Let me know if you're interested!\n\n"
                f"-{app_display_name} from the {app_name.title()} App\n"
            ),
        },
        "themepage": {
            "subject": f"PAID PROMO OPPORTUNITY - {app_name.title()} App",
            "email_md": (
                "hey {name},\n\n"
                f"we run the {app_name.title()} app and we love your theme page. we'd love to do a paid promotion posts with you.\n\n"
                "what is your current RPM rates for posts? looking to do a long term partnership.\n\n"
                f"-{app_display_name} from {app_name.title()}\n"
            ),
            "dm_md": (
                "hey {name},\n\n"
                f"we run the {app_name.title()} app and we love your theme page. we'd love to do a paid promotion posts with you.\n\n"
                "what is your current RPM rates for posts? looking to do a long term partnership.\n\n"
                f"-{app_display_name} from {app_name.title()}\n"
            ),
        },
    }


def get_followup_templates(app_name="pretti", app_config=None):
    """Generate followup templates dynamically based on app configuration."""
    if app_config is None:
        app_config = {}
    
    # Extract app-specific information from config
    app_display_name = app_config.get("from_name", "Abhay Chebium")
    app_url = app_config.get("link_url", "https://a17.so")
    
    return {
        "macro": {
            "subject": f"Re: PAID PROMO OPPORTUNITY - {app_name.title()} App",
            "email_md": (
                "hey {name},\n\n"
                f"just following up on my previous email about the paid promo opportunity with {app_name.title()}!\n\n"
                "we're still looking to work with top beauty creators and would love to have you on board. let me know if you're interested or if you have any questions!\n\n"
                f"{app_name.title()} helps your audience feel more confident with clearer step-by-step looks—feels like something they'd expect you to share.\n\n"
                f"-**{app_display_name}** from the [{app_name.title()} App]({app_url})\n"
            ),
            "dm_md": (
                "hey {name},\n\n"
                f"just following up on my DM about the {app_name.title()} paid promo! still interested in working with you if you're down :)\n\n"
                "lmk!\n\n"
                "it genuinely helps audiences nail looks and feel confident.\n\n"
                f"-{app_display_name} from {app_name.title()}\n"
            ),
        },
        "micro": {
            "subject": f"Re: PAID PROMO OPPORTUNITY - {app_name.title()} App",
            "email_md": (
                "hey {name},\n\n"
                f"following up on my email about the {app_name.title()} paid promo opportunity!\n\n"
                "we think you'd be a great fit and would love to work with you. let me know if you're interested!\n\n"
                f"also, your audience looks to you for guidance—{app_name.title()} makes that guidance tangible.\n\n"
                f"-**{app_display_name}** from the [{app_name.title()} App]({app_url})\n"
            ),
            "dm_md": (
                "hey {name},\n\n"
                f"just following up on the {app_name.title()} collab! still interested if you are :)\n\n"
                "it really serves your audience.\n\n"
                f"-{app_display_name} from {app_name.title()}\n"
            ),
        },
        "submicro": {
            "subject": f"Re: PAID PROMO OPPORTUNITY - {app_name.title()} App",
            "email_md": (
                "hey {name},\n\n"
                f"following up on my email about the {app_name.title()} paid promo opportunity!\n\n"
                "we think you'd be a great fit and would love to work with you. let me know if you're interested!\n\n"
                f"sharing {app_name.title()} helps your audience recreate looks with confidence.\n\n"
                f"-**{app_display_name}** from the [{app_name.title()} App]({app_url})\n"
            ),
            "dm_md": (
                "hey {name},\n\n"
                f"just following up on the {app_name.title()} collab! still interested if you are :)\n\n"
                "they'll appreciate it.\n\n"
                f"-{app_display_name} from {app_name.title()}\n"
            ),
        },
        "ambassador": {
            "subject": f"Re: PAID PROMO OPPORTUNITY - {app_name.title()} App",
            "email_md": (
                "hey {name},\n\n"
                f"just checking in on the ambassador opportunity with {app_name.title()}!\n\n"
                "still looking for creators to post 15 videos/week for $400. let me know if you're interested!\n\n"
                f"-**{app_display_name}** from the [{app_name.title()} App]({app_url})\n"
            ),
            "dm_md": (
                "hey {name},\n\n"
                f"following up on the {app_name.title()} ambassador role! still need creators for $400/week. interested?\n\n"
                f"-{app_display_name} from {app_name.title()}\n"
            ),
        },
        "themepage": {
            "subject": f"Re: PAID PROMO OPPORTUNITY - {app_name.title()} App",
            "email_md": (
                "hey {name},\n\n"
                "following up on the theme page partnership!\n\n"
                "still interested in working with you. what are your rates?\n\n"
                f"-{app_display_name} from {app_name.title()}\n"
            ),
            "dm_md": (
                "hey {name},\n\n"
                "following up on the collab! still interested. what are your rates?\n\n"
                f"-{app_display_name} from {app_name.title()}\n"
            ),
        },
    }


def get_second_followup_templates(app_name="pretti", app_config=None):
    """Generate second followup templates dynamically based on app configuration."""
    if app_config is None:
        app_config = {}
    
    # Extract app-specific information from config
    app_display_name = app_config.get("from_name", "Abhay Chebium")
    app_url = app_config.get("link_url", "https://a17.so")
    
    return {
        "macro": {
            "subject": f"Re: PAID PROMO OPPORTUNITY - {app_name.title()} App",
            "email_md": (
                "hey {name},\n\n"
                f"hope you're doing well! just wanted to follow up one more time about the {app_name.title()} paid promo opportunity.\n\n"
                "we're still looking for top beauty creators and would love to work with you. no pressure if you're not interested, just wanted to make sure you saw this!\n\n"
                f"quick note: {app_name.title()} is a real confidence boost for audiences—worth sharing.\n\n"
                "let me know either way :)\n\n"
                f"-**{app_display_name}** from the [{app_name.title()} App]({app_url})\n"
            ),
            "dm_md": (
                "hey {name},\n\n"
                f"hope you're doing well! just wanted to follow up one more time about the {app_name.title()} promo.\n\n"
                "no pressure if you're not interested, just wanted to make sure you saw this!\n\n"
                "your audience would get a lot from it.\n\n"
                f"-{app_display_name} from {app_name.title()}\n"
            ),
        },
        "micro": {
            "subject": f"Re: PAID PROMO OPPORTUNITY - {app_name.title()} App",
            "email_md": (
                "hey {name},\n\n"
                f"hope you're doing well! just wanted to follow up one more time about the {app_name.title()} collaboration.\n\n"
                "we think you'd be perfect for this and would love to work with you. no pressure if you're not interested!\n\n"
                "it meaningfully serves your audience's confidence and routines.\n\n"
                "let me know either way :)\n\n"
                f"-**{app_display_name}** from the [{app_name.title()} App]({app_url})\n"
            ),
            "dm_md": (
                "hey {name},\n\n"
                f"hope you're doing well! just wanted to follow up one more time about {app_name.title()}.\n\n"
                "no pressure if you're not interested!\n\n"
                "it genuinely helps your audience.\n\n"
                f"-{app_display_name} from {app_name.title()}\n"
            ),
        },
        "submicro": {
            "subject": f"Re: PAID PROMO OPPORTUNITY - {app_name.title()} App",
            "email_md": (
                "hey {name},\n\n"
                f"hope you're doing well! just wanted to follow up one more time about the {app_name.title()} collaboration.\n\n"
                "we think you'd be perfect for this and would love to work with you. no pressure if you're not interested!\n\n"
                "let me know either way :)\n\n"
                f"-**{app_display_name}** from the [{app_name.title()} App]({app_url})\n"
            ),
            "dm_md": (
                "hey {name},\n\n"
                f"hope you're doing well! just wanted to follow up one more time about {app_name.title()}.\n\n"
                "no pressure if you're not interested!\n\n"
                f"-{app_display_name} from {app_name.title()}\n"
            ),
        },
        "ambassador": {
            "subject": f"Re: PAID PROMO OPPORTUNITY - {app_name.title()} App",
            "email_md": (
                "hey {name},\n\n"
                f"hope you're doing well! just wanted to follow up one more time about the {app_name.title()} ambassador opportunity.\n\n"
                "still need creators for 15 videos/week at $400. no pressure if you're not interested!\n\n"
                "let me know either way :)\n\n"
                f"-**{app_display_name}** from the [{app_name.title()} App]({app_url})\n"
            ),
            "dm_md": (
                "hey {name},\n\n"
                f"hope you're doing well! just wanted to follow up one more time about the ambassador role.\n\n"
                "no pressure if you're not interested!\n\n"
                f"-{app_display_name} from {app_name.title()}\n"
            ),
        },
        "themepage": {
            "subject": f"Re: PAID PROMO OPPORTUNITY - {app_name.title()} App",
            "email_md": (
                "hey {name},\n\n"
                "hope you're doing well! just wanted to follow up one more time about the theme page partnership.\n\n"
                "still interested in working with you. no pressure if you're not interested!\n\n"
                "let me know either way :)\n\n"
                f"-{app_display_name} from {app_name.title()}\n"
            ),
            "dm_md": (
                f"hey {{name}}, hope you're doing well! just wanted to follow up one more time about the collab. no pressure if you're not interested! -{app_display_name} from {app_name.title()}"
            ),
        },
    }


def get_third_followup_templates(app_name="pretti", app_config=None):
    """Generate third followup templates dynamically based on app configuration."""
    if app_config is None:
        app_config = {}
    
    # Extract app-specific information from config
    app_display_name = app_config.get("from_name", "Abhay Chebium")
    app_url = app_config.get("link_url", "https://a17.so")
    
    return {
        "macro": {
            "subject": f"Re: Final follow-up - {app_name.title()} App",
            "email_md": (
                "hey {name},\n\n"
                f"this is my final follow-up about the {app_name.title()} paid promo opportunity.\n\n"
                "if you're interested, great! if not, no worries at all - I'll stop reaching out.\n\n"
                f"either way, {app_name.title()} really does help audiences feel more confident.\n\n"
                "thanks for your time!\n\n"
                f"-**{app_display_name}** from the [{app_name.title()} App]({app_url})\n"
            ),
            "dm_md": (
                "hey {name},\n\n"
                f"this is my final follow-up about the {app_name.title()} promo.\n\n"
                "if you're interested, great! if not, no worries - I'll stop reaching out.\n\n"
                "last note: it's a solid value for your audience.\n\n"
                "thanks for your time!\n\n"
                f"-{app_display_name} from {app_name.title()}\n"
            ),
        },
        "micro": {
            "subject": f"Re: Final follow-up - {app_name.title()} App",
            "email_md": (
                "hey {name},\n\n"
                f"this is my final follow-up about the {app_name.title()} collaboration.\n\n"
                "if you're interested, great! if not, no worries at all - I'll stop reaching out.\n\n"
                "just leaving this here because your audience would genuinely benefit.\n\n"
                "thanks for your time!\n\n"
                f"-**{app_display_name}** from the [{app_name.title()} App]({app_url})\n"
            ),
            "dm_md": (
                "hey {name},\n\n"
                f"this is my final follow-up about {app_name.title()}.\n\n"
                "if you're interested, great! if not, no worries - I'll stop reaching out.\n\n"
                "felt aligned with how you support your audience.\n\n"
                "thanks for your time!\n\n"
                f"-{app_display_name} from {app_name.title()}\n"
            ),
        },
        "submicro": {
            "subject": f"Re: Final follow-up - {app_name.title()} App",
            "email_md": (
                "hey {name},\n\n"
                f"this is my final follow-up about the {app_name.title()} collaboration.\n\n"
                "if you're interested, great! if not, no worries at all - I'll stop reaching out.\n\n"
                "thanks for your time!\n\n"
                f"-**{app_display_name}** from the [{app_name.title()} App]({app_url})\n"
            ),
            "dm_md": (
                "hey {name},\n\n"
                f"this is my final follow-up about {app_name.title()}.\n\n"
                "if you're interested, great! if not, no worries - I'll stop reaching out.\n\n"
                "thanks for your time!\n\n"
                f"-{app_display_name} from {app_name.title()}\n"
            ),
        },
        "ambassador": {
            "subject": f"Re: Final follow-up - {app_name.title()} App",
            "email_md": (
                "hey {name},\n\n"
                f"this is my final follow-up about the {app_name.title()} ambassador opportunity.\n\n"
                "if you're interested, great! if not, no worries at all - I'll stop reaching out.\n\n"
                "thanks for your time!\n\n"
                f"-**{app_display_name}** from the [{app_name.title()} App]({app_url})\n"
            ),
            "dm_md": (
                "hey {name},\n\n"
                f"this is my final follow-up about the ambassador role.\n\n"
                "if you're interested, great! if not, no worries - I'll stop reaching out.\n\n"
                "thanks for your time!\n\n"
                f"-{app_display_name} from {app_name.title()}\n"
            ),
        },
        "themepage": {
            "subject": f"Re: Final follow-up - {app_name.title()} App",
            "email_md": (
                "hey {name},\n\n"
                "this is my final follow-up about the theme page partnership.\n\n"
                "if you're interested, great! if not, no worries at all - I'll stop reaching out.\n\n"
                "thanks for your time!\n\n"
                f"-{app_display_name} from {app_name.title()}\n"
            ),
            "dm_md": (
                f"hey {{name}}, this is my final follow-up about the collab. if you're interested, great! if not, no worries - I'll stop reaching out. thanks for your time! -{app_display_name} from {app_name.title()}"
            ),
        },
    }


# Legacy compatibility - create static templates for backward compatibility
TEMPLATES = get_templates()
FOLLOWUP_TEMPLATES = get_followup_templates()
SECOND_FOLLOWUP_TEMPLATES = get_second_followup_templates()
THIRD_FOLLOWUP_TEMPLATES = get_third_followup_templates()


