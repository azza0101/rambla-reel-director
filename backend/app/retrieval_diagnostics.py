"""Structured empty states shared by workers and the curation UI."""
MESSAGES={
    'available':'Candidates are ready for review.',
    'not_requested':'No new retrieval requested for this visual action.',
    'provider_not_configured':'Provider not configured.',
    'provider_request_failed':'The provider request failed. See retrieval details.',
    'zero_provider_hits':'The provider returned no matches for these queries.',
    'no_hd_candidates':'Matches were found, but none had usable image dimensions.',
    'preview_download_failed':'Matches were found, but their previews could not be downloaded.',
    'ranker_unavailable':'Qwen visual ranking is unavailable. Relevance needs review.',
    'duplicate_only':'Matches repeat visuals already shown in other beats.',
    'visually_rejected':'Sampled content did not sufficiently match this shot.',
    'clip_localization_failed':'Sources were found, but no relevant playable window could be prepared.',
}


def empty_reason(c):
    if c.get('accepted'):code='available'
    elif c.get('provider_configured') is False:code='provider_not_configured'
    elif c.get('requests_failed') and not c.get('raw'):code='provider_request_failed'
    elif not c.get('raw'):code='zero_provider_hits'
    elif c.get('clip_failed'):code='clip_localization_failed'
    elif not c.get('hd'):code='no_hd_candidates'
    elif not c.get('preview') and c.get('preview_failed'):code='preview_download_failed'
    elif c.get('ranker_unavailable'):code='ranker_unavailable'
    elif c.get('duplicates') and not c.get('rejected'):code='duplicate_only'
    else:code='visually_rejected'
    return {'code':code,'message':MESSAGES[code],'counts':c}


def image_diagnostic(row):
    if row.get('visual_action') in {'KEEP_TALKING_HEAD','CONTINUE_PREVIOUS_VISUAL'}:return {'code':'not_requested','message':MESSAGES['not_requested'],'counts':{}}
    counts=row.get('counts',{'raw':row.get('raw_count',0),'hd':1,'preview':1,'rejected':len(row.get('rejected_candidates',[]))})
    return empty_reason({**counts,'accepted':len(row.get('candidates',[]))})


def video_diagnostic(rows,provider,configured=True):
    attempts=[a for r in rows for a in r.get('search_attempts',[]) if ('pexels' in a.get('provider','').lower())==(provider=='pexels')]
    errors=[e for r in rows for e in r.get('errors',[]) if isinstance(e,dict) and e.get('provider')==provider]
    counts={'accepted':sum(c.get('provider',c.get('source'))==provider for r in rows for c in r.get('candidates',[])),'provider_configured':configured,'raw':sum(a.get('hits',0) for a in attempts),
        'requests_failed':sum(e.get('code') not in {'clip_preview_failed','poster_failed'} for e in errors),
        'clip_failed':sum(e.get('code')=='clip_preview_failed' for e in errors),'hd':1,'preview':1,
        'ranker_unavailable':any(r.get('ranking_warning') for r in rows),
        'duplicates':sum(r.get('duplicates_rejected',0) for r in rows),
        'rejected':sum(len(r.get('rejected_candidates',[])) for r in rows)}
    return empty_reason(counts)
