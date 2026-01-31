

def get_templates(app_name="HARDMAXX", app_config=None):
    """Generate templates dynamically based on app configuration."""
    if app_config is None:
        app_config = {}
    
    # Extract app-specific information from config
    app_display_name = app_config.get("from_name", "Abhay Chebium")
    app_url = app_config.get("link_url", "https://apps.apple.com/us/app/hardmaxx-transform-now/id6756548399")
    
    # Common sections
    INTRO = (
        f"{app_name.upper()} is a peptide transformation app that uses AI to help you with your peptide cycle.\n\n"
    )

    IMAGE_LINK = (
        "here are some images of the product:\n"
        "https://drive.google.com/drive/u/0/folders/1JWJ4bfA1a55G6Ifp4Trw7WZCXENPo7pu\n\n"
    )

    DELIVERABLES_BULLETS = (
        "here is a brief about deliverables + rate:\n"
        "- $1 CPM ($1 for every 1,000 views)\n"
        "- $350 Max Payout per video\n"
        "- 10k Views Minimum to qualify\n"
        "- Payouts every 1 - 2 weeks\n"
        "- 4-20 posts per month based on your schedule\n\n"
    )

    DELIVERABLES_LINK = (
        "here is a brief about deliverables + rate: "
        "https://www.notion.so/HARDMAXX-Clipping-Program-2c739b5e840f800e826bc1cc0569aea3\n\n"
    )

    # Variant specific texts
    # Keeping original variant text intent but fitting into new flow
    MACRO_TEXT = "we're inviting a few, bigtime self-improvement creators who have a cultlike following to try it out & pay you to promote the app.\n\n"
    MICRO_TEXT = "we're inviting a few, niche self-improvement creators who have a cultlike following to try it out & pay you to promote the app.\n\n"
    AMBASSADOR_TEXT = "we're looking for creators with great energy to make brand new tiktok accounts and post 15 videos per week. I think you'd be a great fit for it! would you be interested?\n\n"
    
    # For themepages, user requested: "for the themepages there should be no bullets" matches the link
    THEMEPAGE_TEXT = f"we run {app_name.upper()} and love your theme page. we'd love to get featured posts with you.\n\n"

    def build_body(variant_text, includes_deliverables=False, is_themepage=False):
        body = f"hey {{name}},\n\npaid promo?\n\n{INTRO}{variant_text}".lstrip()
        if includes_deliverables:
            if is_themepage:
                body += DELIVERABLES_LINK
            else:
                body += DELIVERABLES_BULLETS
        
        body += "let me know if you're interested.\n\n"
        
        if is_themepage:
             # Theme pages had a slightly different footer in original, but standardizing to the requested format for now or keeping close to original?
             # User prompt image signoff: "- Abhay Chebium from the HARDMAXX App (link)"
             # Original code signoff: "- {app_display_name} from the {app_name.upper()} App ({app_url})\n"
             pass

        signoff = f"- {app_display_name} from the {app_name.upper()} App"
        if includes_deliverables: # Only email gets the link in signature? 
            # Prompt: "The link should only be there in the email script, not in the DM script" (referring to deliverables link AND app link?)
            # Prompt: "The link should only be there in the email script... Same thing for theme pages... the link should only be there in the email script, not in the DM script."
            # The prompt says: "app link... on the DM it should have no link of the app."
            signoff += f" ({app_url})"
        
        return body + signoff + "\n"

    return {
        "macro": {
            "subject": f"PAID PROMO OPPORTUNITY - {app_name.upper()} App",
            "email_md": build_body(MACRO_TEXT, includes_deliverables=False, is_themepage=False),
            "dm_md": build_body(MACRO_TEXT, includes_deliverables=False, is_themepage=False),
        },
        "micro": {
            "subject": f"PAID PROMO OPPORTUNITY - {app_name.upper()} App",
            "email_md": build_body(MICRO_TEXT, includes_deliverables=True, is_themepage=False),
            "dm_md": build_body(MICRO_TEXT, includes_deliverables=False, is_themepage=False),
        },
        "submicro": {
            "subject": f"PAID PROMO OPPORTUNITY - {app_name.upper()} App",
            "email_md": build_body(MICRO_TEXT, includes_deliverables=True, is_themepage=False), # Submicro uses micro text usually
            "dm_md": build_body(MICRO_TEXT, includes_deliverables=False, is_themepage=False),
        },
        "ambassador": {
            "subject": f"PAID PROMO OPPORTUNITY - {app_name.upper()} App",
            "email_md": build_body(MICRO_TEXT, includes_deliverables=True, is_themepage=False),
            "dm_md": build_body(MICRO_TEXT, includes_deliverables=False, is_themepage=False),
        },
        "themepage": {
            "subject": f"PAID PROMO OPPORTUNITY - {app_name.upper()} App", # Subject changed to match others or keep old? Prompt says "base template for hardmaxx outreach scripts", implies for all.
            "email_md": build_body(THEMEPAGE_TEXT, includes_deliverables=True, is_themepage=True),
            "dm_md": build_body(THEMEPAGE_TEXT, includes_deliverables=False, is_themepage=True),
        },
    }


def get_followup_templates(app_name="HARDMAXX", app_config=None):
    """Generate followup templates dynamically based on app configuration."""
    if app_config is None:
        app_config = {}
    
    # Extract app-specific information from config
    app_display_name = app_config.get("from_name", "Ad Akella")
    app_url = app_config.get("link_url", "https://a17.so")
    
    return {
        "macro": {
            "subject": f"Re: PAID PROMO OPPORTUNITY - {app_name.upper()} App",
            "email_md": (
                "hey {name},\n\n"
                f"just following up on the {app_name.upper()} paid promo!\n\n"
                "we've got more creators onboard since we last talked and would love to have you join. still interested?\n\n"
                f"since {app_name.upper()} helps people build better habits fast, it really serves your audience—feels like the kind of tool they'd expect you to share.\n\n"
                "let me know if you're interested.\n\n"
                f"- {app_display_name} from the {app_name.upper()} App ({app_url})\n"
            ),
            "dm_md": (
                "hey {name},\n\n"
                f"following up on the {app_name.upper()} promo! still interested in working with you if you're down.\n\n"
                f"it genuinely helps audiences build better habits—felt like something they'd expect from you.\n\n"
                "let me know if you're interested.\n\n"
                f"- {app_display_name} from the {app_name.upper()} App\n"
            ),
        },
        "micro": {
            "subject": f"Re: PAID PROMO OPPORTUNITY - {app_name.upper()} App",
            "email_md": (
                "hey {name},\n\n"
                f"just checking in on the {app_name.upper()} collaboration!\n\n"
                "we're still looking to work with niche creators like you. let me know if you're interested!\n\n"
                f"your audience follows you to get better—{app_name.upper()} makes that easier, so sharing it really serves them.\n\n"
                f"- {app_display_name} from the {app_name.upper()} App ({app_url})\n"
            ),
            "dm_md": (
                "hey {name},\n\n"
                f"following up on {app_name.upper()}! still down to work with you if you're interested.\n\n"
                "feels aligned with how you show up for your audience.\n\n"
                f"- {app_display_name} from the {app_name.upper()} App\n"
            ),
        },
        "submicro": {
            "subject": f"Re: PAID PROMO OPPORTUNITY - {app_name.upper()} App",
            "email_md": (
                "hey {name},\n\n"
                f"just checking in on the {app_name.upper()} collaboration!\n\n"
                "we're still looking to work with niche creators like you. let me know if you're interested!\n\n"
                f"sharing {app_name.upper()} genuinely helps your audience build better habits.\n\n"
                f"- {app_display_name} from the {app_name.upper()} App ({app_url})\n"
            ),
            "dm_md": (
                "hey {name},\n\n"
                f"following up on {app_name.upper()}! still down to work with you if you're interested.\n\n"
                "it's the kind of thing your audience expects from you.\n\n"
                f"- {app_display_name} from the {app_name.upper()} App\n"
            ),
        },
        "ambassador": {
            "subject": f"Re: PAID PROMO OPPORTUNITY - {app_name.upper()} App",
            "email_md": (
                "hey {name},\n\n"
                f"just checking in on the {app_name.upper()} collaboration!\n\n"
                "we're still looking to work with niche creators like you. let me know if you're interested!\n\n"
                f"sharing {app_name.upper()} genuinely helps your audience build better habits.\n\n"
                f"- {app_display_name} from the {app_name.upper()} App ({app_url})\n"
            ),
            "dm_md": (
                "hey {name},\n\n"
                f"following up on {app_name.upper()}! still down to work with you if you're interested.\n\n"
                "it's the kind of thing your audience expects from you.\n\n"
                f"- {app_display_name} from the {app_name.upper()} App\n"
            ),
        },
        "themepage": {
            "subject": f"Re: {app_name.upper()} x Theme Page DM",
            "email_md": (
                "hey {name},\n\n"
                "following up on the theme page partnership!\n\n"
                "still interested in working with you. what are your rates?\n\n"
                f"- {app_display_name} from the {app_name.upper()} App ({app_url})\n"
            ),
            "dm_md": (
                f"hey {{name}}, following up on the collab! what are your rates? - {app_display_name} from the {app_name.upper()} App"
            ),
        },
    }


def get_second_followup_templates(app_name="HARDMAXX", app_config=None):
    """Generate second followup templates dynamically based on app configuration."""
    if app_config is None:
        app_config = {}
    
    # Extract app-specific information from config
    app_display_name = app_config.get("from_name", "Ad Akella")
    app_url = app_config.get("link_url", "https://a17.so")
    
    return {
        "macro": {
            "subject": f"Re: PAID PROMO OPPORTUNITY - {app_name.upper()} App",
            "email_md": (
                "hey {name},\n\n"
                f"hope you're doing well! just wanted to follow up one more time about the {app_name.upper()} paid promo opportunity.\n\n"
                "we're still looking for creators and would love to work with you. no pressure if you're not interested, just wanted to make sure you saw this!\n\n"
                f"quick note: {app_name.upper()} helps people level up—sharing it is a real value-add for your audience.\n\n"
                "let me know either way :)\n\n"
                f"- {app_display_name} from the {app_name.upper()} App ({app_url})\n"
            ),
            "dm_md": (
                "hey {name},\n\n"
                f"hope you're doing well! just wanted to follow up one more time about the {app_name.upper()} promo.\n\n"
                "no pressure if you're not interested, just wanted to make sure you saw this!\n\n"
                "your audience would get a lot from it.\n\n"
                f"- {app_display_name} from the {app_name.upper()} App\n"
            ),
        },
        "micro": {
            "subject": f"Re: PAID PROMO OPPORTUNITY - {app_name.upper()} App",
            "email_md": (
                "hey {name},\n\n"
                f"hope you're doing well! just wanted to follow up one more time about the {app_name.upper()} collaboration.\n\n"
                "we think you'd be perfect for this and would love to work with you. no pressure if you're not interested!\n\n"
                f"it meaningfully serves your audience's self-improvement goals.\n\n"
                "let me know either way :)\n\n"
                f"- {app_display_name} from the {app_name.upper()} App ({app_url})\n"
            ),
            "dm_md": (
                "hey {name},\n\n"
                f"hope you're doing well! just wanted to follow up one more time about {app_name.upper()}.\n\n"
                "no pressure if you're not interested!\n\n"
                "it genuinely helps your audience.\n\n"
                f"- {app_display_name} from the {app_name.upper()} App\n"
            ),
        },
        "submicro": {
            "subject": f"Re: PAID PROMO OPPORTUNITY - {app_name.upper()} App",
            "email_md": (
                "hey {name},\n\n"
                f"hope you're doing well! just wanted to follow up one more time about the {app_name.upper()} collaboration.\n\n"
                "we think you'd be perfect for this and would love to work with you. no pressure if you're not interested!\n\n"
                "let me know either way :)\n\n"
                f"- {app_display_name} from the {app_name.upper()} App ({app_url})\n"
            ),
            "dm_md": (
                "hey {name},\n\n"
                f"hope you're doing well! just wanted to follow up one more time about {app_name.upper()}.\n\n"
                "no pressure if you're not interested!\n\n"
                f"- {app_display_name} from the {app_name.upper()} App\n"
            ),
        },
        "ambassador": {
            "subject": f"Re: PAID PROMO OPPORTUNITY - {app_name.upper()} App",
            "email_md": (
                "hey {name},\n\n"
                f"hope you're doing well! just wanted to follow up one more time about the {app_name.upper()} collaboration.\n\n"
                "we think you'd be perfect for this and would love to work with you. no pressure if you're not interested!\n\n"
                "let me know either way :)\n\n"
                f"- {app_display_name} from the {app_name.upper()} App ({app_url})\n"
            ),
            "dm_md": (
                "hey {name},\n\n"
                f"hope you're doing well! just wanted to follow up one more time about {app_name.upper()}.\n\n"
                "no pressure if you're not interested!\n\n"
                f"- {app_display_name} from the {app_name.upper()} App\n"
            ),
        },
        "themepage": {
            "subject": f"Re: {app_name.upper()} x Theme Page DM",
            "email_md": (
                "hey {name},\n\n"
                "hope you're doing well! just wanted to follow up one more time about the theme page partnership.\n\n"
                "still interested in working with you. no pressure if you're not interested!\n\n"
                "let me know either way :)\n\n"
                f"- {app_display_name} from the {app_name.upper()} App ({app_url})\n"
            ),
            "dm_md": (
                f"hey {{name}}, hope you're doing well! just wanted to follow up one more time about the collab. no pressure if you're not interested! - {app_display_name} from the {app_name.upper()} App"
            ),
        },
    }


def get_third_followup_templates(app_name="HARDMAXX", app_config=None):
    """Generate third followup templates dynamically based on app configuration."""
    if app_config is None:
        app_config = {}
    
    # Extract app-specific information from config
    app_display_name = app_config.get("from_name", "Ad Akella")
    app_url = app_config.get("link_url", "https://a17.so")
    
    return {
        "macro": {
            "subject": f"Re: Final follow-up - {app_name.upper()} App",
            "email_md": (
                "hey {name},\n\n"
                f"this is my final follow-up about the {app_name.upper()} paid promo opportunity.\n\n"
                "if you're interested, great! if not, no worries at all - I'll stop reaching out.\n\n"
                f"either way, wanted to flag that {app_name.upper()} really does help audiences build better habits.\n\n"
                "thanks for your time!\n\n"
                f"- {app_display_name} from the {app_name.upper()} App ({app_url})\n"
            ),
            "dm_md": (
                "hey {name},\n\n"
                f"this is my final follow-up about the {app_name.upper()} promo.\n\n"
                "if you're interested, great! if not, no worries - I'll stop reaching out.\n\n"
                "last note: it's a solid value for your audience.\n\n"
                "thanks for your time!\n\n"
                f"- {app_display_name} from the {app_name.upper()} App\n"
            ),
        },
        "micro": {
            "subject": f"Re: Final follow-up - {app_name.upper()} App",
            "email_md": (
                "hey {name},\n\n"
                f"this is my final follow-up about the {app_name.upper()} collaboration.\n\n"
                "if you're interested, great! if not, no worries at all - I'll stop reaching out.\n\n"
                "just leaving this here because your audience would genuinely benefit.\n\n"
                "thanks for your time!\n\n"
                f"- {app_display_name} from the {app_name.upper()} App ({app_url})\n"
            ),
            "dm_md": (
                "hey {name},\n\n"
                f"this is my final follow-up about {app_name.upper()}.\n\n"
                "if you're interested, great! if not, no worries - I'll stop reaching out.\n\n"
                "felt aligned with how you support your audience.\n\n"
                "thanks for your time!\n\n"
                f"- {app_display_name} from the {app_name.upper()} App\n"
            ),
        },
        "submicro": {
            "subject": f"Re: Final follow-up - {app_name.upper()} App",
            "email_md": (
                "hey {name},\n\n"
                f"this is my final follow-up about the {app_name.upper()} collaboration.\n\n"
                "if you're interested, great! if not, no worries at all - I'll stop reaching out.\n\n"
                "thanks for your time!\n\n"
                f"- {app_display_name} from the {app_name.upper()} App ({app_url})\n"
            ),
            "dm_md": (
                "hey {name},\n\n"
                f"this is my final follow-up about {app_name.upper()}.\n\n"
                "if you're interested, great! if not, no worries - I'll stop reaching out.\n\n"
                "thanks for your time!\n\n"
                f"- {app_display_name} from the {app_name.upper()} App\n"
            ),
        },
        "ambassador": {
            "subject": f"Re: Final follow-up - {app_name.upper()} App",
            "email_md": (
                "hey {name},\n\n"
                f"this is my final follow-up about the {app_name.upper()} collaboration.\n\n"
                "if you're interested, great! if not, no worries at all - I'll stop reaching out.\n\n"
                "thanks for your time!\n\n"
                f"- {app_display_name} from the {app_name.upper()} App ({app_url})\n"
            ),
            "dm_md": (
                "hey {name},\n\n"
                f"this is my final follow-up about {app_name.upper()}.\n\n"
                "if you're interested, great! if not, no worries - I'll stop reaching out.\n\n"
                "thanks for your time!\n\n"
                f"- {app_display_name} from the {app_name.upper()} App\n"
            ),
        },
        "themepage": {
            "subject": f"Re: Final follow-up - {app_name.upper()} App",
            "email_md": (
                "hey {name},\n\n"
                "this is my final follow-up about the theme page partnership.\n\n"
                "if you're interested, great! if not, no worries at all - I'll stop reaching out.\n\n"
                "thanks for your time!\n\n"
                f"- {app_display_name} from the {app_name.upper()} App ({app_url})\n"
            ),
            "dm_md": (
                f"hey {{name}}, this is my final follow-up about the collab. if you're interested, great! if not, no worries - I'll stop reaching out. thanks for your time! - {app_display_name} from the {app_name.upper()} App"
            ),
        },
    }


# Legacy compatibility - create static templates for backward compatibility
TEMPLATES = get_templates()
FOLLOWUP_TEMPLATES = get_followup_templates()
SECOND_FOLLOWUP_TEMPLATES = get_second_followup_templates()
THIRD_FOLLOWUP_TEMPLATES = get_third_followup_templates()


