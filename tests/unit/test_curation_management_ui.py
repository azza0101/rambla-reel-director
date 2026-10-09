from pathlib import Path

from fastapi.testclient import TestClient


def test_management_ui_exposes_project_library_clean_media_and_per_beat_research():
    from backend.app.curation_ui_v2 import render_curation_page_v2

    html = render_curation_page_v2("management-test")
    for text in (
        "PROJECTS", "CLEAN MEDIA", "NEW SEARCH", "ADD TIKTOK + IG",
        "Project Library", "Disk usage", "RENAME", "DELETE",
    ):
        assert text in html
    assert "api('/projects')" in html
    assert "method:'PATCH'" in html
    assert "method:'DELETE'" in html
    assert "/media/clean" in html
    assert "/research`" in html or "/research" in html
    assert "researchBeatV2('replace')" in html
    assert "researchBeatV2('append',providers)" in html
    assert "startStage('analyze')" not in html[html.index("async function researchBeatV2"):html.index("function installManagementV2")]


def test_broll_and_director_show_real_progress_and_provider_checks():
    from backend.app.curation_ui_v2 import render_curation_page_v2

    html = render_curation_page_v2("progress-ui")
    for marker in ("brollProgressBarV34", "brollSourceChecksV34", "directorProgressBarV34",
                   "renderBrollProgressV34", "renderDirectorProgressV34"):
        assert marker in html
    assert "Creazione piano in corso" in html
    assert "planStatus==='running'?'Creazione piano in corso':'Plan complete'" in html
    assert "${done.has(key)?'✓':'○'} ${label}" in html
    assert "workspace-backup" in html


def test_resolve_delivery_waits_for_bridge_acknowledgement_before_green_success():
    from backend.app.curation_ui_v2 import render_curation_page_v2

    html = render_curation_page_v2("resolve-delivery")
    assert "resolveDeliveryCheckV33" in html
    assert "bridge_received_at" in html
    assert "ESPORTATO SU RESOLVE" in html
    assert "PACCHETTO PRONTO · ATTESA RICEZIONE" in html
    assert "PREPARAZIONE PER RESOLVE" in html


def test_management_ui_project_delete_and_clean_have_confirmations():
    from backend.app.curation_ui_v2 import render_curation_page_v2

    html = render_curation_page_v2("management-test")
    assert "confirm(" in html
    assert "Transcript and editorial plan stay safe" in html
    assert "permanently delete" in html


def test_management_ui_keeps_initial_shelves_compact_but_supports_show_more():
    from backend.app.curation_ui_v2 import render_curation_page_v2

    html = render_curation_page_v2("management-test")
    assert "SHOW MORE" in html
    assert "expandedShelvesV2" in html


def test_product_server_serves_management_curation_page(tmp_path):
    from backend.app.curation_server import create_app

    root = tmp_path / "projects"
    allowed = tmp_path / "allowed"
    allowed.mkdir()
    client = TestClient(create_app(
        project_root=root,
        allowed_media_roots=[allowed],
        probe_runner=lambda _: {"duration": 1, "fps": 25, "width": 1080, "height": 1920, "has_audio": False},
    ))
    response = client.get("/curation")
    assert response.status_code == 200
    assert "PROJECTS" in response.text
    assert "CLEAN MEDIA" in response.text
    assert "NEW SEARCH" in response.text
    assert "ADD TIKTOK + IG" in response.text


def test_acceptance_launcher_starts_product_server():
    launcher = Path("tools/start_curation_acceptance.ps1").read_text(encoding="utf-8")
    assert "backend.app.curation_server:app" in launcher
    assert "RAMBLA_ENABLE_VERTICAL_SOCIAL = '1'" in launcher


def test_product_ui_has_global_social_only_search_next_to_broll():
    from backend.app.curation_ui_v2 import render_curation_page_v2

    html = render_curation_page_v2("social-global")
    assert 'id="findVideos"' in html
    assert 'id="findSocial"' in html
    assert html.index('id="findVideos"') < html.index('id="findSocial"') < html.index('id="findImages"')
    assert "FIND SOCIAL" in html
    assert "startSelectedSocialV5" in html


def test_visual_beats_offer_broll_only_view_and_global_search_opens_it():
    from backend.app.curation_ui_v2 import render_curation_page_v2

    html = render_curation_page_v2("broll-scenes")
    assert 'data-filter="broll"' in html
    assert "B-ROLL SCENES" in html
    assert "state.filter==='broll'?c.action==='BROLL'" in html
    assert "function prepareBrollViewV24()" in html
    assert "findVideosBaseV24" in html


def test_media_cards_preserve_source_aspect_ratio_and_use_real_source_buttons():
    from backend.app.curation_ui_v2 import render_curation_page_v2

    html = render_curation_page_v2("media-card-redesign")
    assert ".card:not(.portraitSocialV6)>img,.card:not(.portraitSocialV6)>video" in html
    assert "height:auto" in html
    assert "object-fit:contain" in html
    assert ".sourceButtonV9{display:inline-flex" in html
    assert "Apri fonte" in html


def test_provider_pagination_controls_live_in_the_provider_header():
    from backend.app.curation_ui_v2 import render_curation_page_v2

    html = render_curation_page_v2("provider-header")
    assert "providerHeaderV25" in html
    assert "providerControlsV25" in html
    assert "header.appendChild(bar)" in html
    assert "galleryPageV10" in html
    assert "gallerySearchV10" in html


def test_provider_gallery_restores_research_round_from_project_artifact():
    from backend.app.curation_ui_v2 import render_curation_page_v2

    html = render_curation_page_v2("persisted-round")
    assert "chunk.research_round" in html
    assert "Math.max(g.round" in html


def test_active_project_name_is_editable_and_autosaved():
    from backend.app.curation_ui_v2 import render_curation_page_v2

    html = render_curation_page_v2("editable-project-name")
    assert 'id="projectNameV25"' in html
    assert "saveProjectNameV25" in html
    assert "method:'PATCH'" in html
    assert "projectNameV25" in html


def test_every_broll_video_provider_has_incremental_search_controls():
    from backend.app.curation_ui_v2 import render_curation_page_v2

    html = render_curation_page_v2("all-provider-pagination")
    for provider in ("youtube", "youtube_shorts", "pexels", "envato", "web_video", "tiktok", "instagram"):
        assert f"'{provider}'" in html
    assert "installProviderGalleriesV26" in html
    assert "＋ Cerca fino a 6 nuove" in html


def test_image_results_use_the_same_ordered_compact_gallery_as_other_sources():
    from backend.app.curation_ui_v2 import render_curation_page_v2

    html = render_curation_page_v2("ordered-image-gallery")
    assert "images:'images'" in html
    assert "#webNewsVideosV2,#images" in html
    assert ".providerFold #images .card" in html


def test_visual_plan_is_collapsed_inside_each_beat():
    from backend.app.curation_ui_v2 import render_curation_page_v2

    html = render_curation_page_v2("collapsed-plan")
    assert 'class="visualPlanBoxV26"' in html
    assert "Visual plan" in html
    assert "<details" in html


def test_broll_sources_remain_selectable_before_clip_materialization():
    from backend.app.curation_ui_v2 import render_curation_page_v2

    html = render_curation_page_v2("select-sources")
    assert 'class="select">${selected?' in html
    assert 'class="select" ${a.selectable===false?"disabled":""}' not in html


def test_workflow_steps_expose_persistent_completion_indicators():
    from backend.app.curation_ui_v2 import render_curation_page_v2

    html = render_curation_page_v2("status-test")
    for indicator in (
        "analysisCompleteV12",
        "planCompleteV12",
        "videoCompleteV12",
        "socialCompleteV12",
        "imagesCompleteV12",
    ):
        assert f'id="{indicator}"' in html
    assert "function syncWorkflowStatusV12()" in html
    assert "retrieval_diagnostics" in html


def test_numbered_workflow_is_collapsed_and_opens_only_the_next_step():
    from backend.app.curation_ui_v2 import render_curation_page_v2

    html = render_curation_page_v2("progressive-workflow")
    assert "installWorkflowAccordionV42" in html
    assert "workflowCollapsedV42" in html
    assert "openOnlyWorkflowStepV42" in html
    assert "nextWorkflowStepV42" in html
    assert "continueWorkflowV15" in html
    assert "header.prepend(chevron)" in html
    assert "titleRow.append(chevron,nestedHeading)" in html
    assert "open?'▼':'▶'" in html
    assert "border-radius:8px" in html
    assert '<section class="panel workflowSceneHeaderV44" data-workflow-step-v42="5"><h2 id="sceneWorkspaceHeading">5 · Visual beats · testo e B-roll</h2></section>' in html
    assert ".workflowNextV42{border-color" not in html
    assert "linear-gradient(180deg,#0b2427,#081b1e)" in html
    for step in range(1, 8):
        assert f'data-workflow-step-v42="{step}"' in html
    assert "else shell.after(bar);" in html


def test_workspace_session_restores_across_ports_and_periodically_autosaves():
    from backend.app.curation_ui_v2 import render_curation_page_v2

    html = render_curation_page_v2("resume-test")
    assert "'/workspace-session'" in html
    assert "saveWorkspaceSessionV13" in html
    assert "restoreWorkspaceSessionV13" in html
    assert "setInterval(saveWorkspaceSessionV13,15000)" in html
    assert "visibilitychange" in html
    assert "active_chunk_id" in html


def test_management_ui_keeps_existing_layout_and_adds_api_director_controls():
    from backend.app.curation_ui_v2 import render_curation_page_v2

    html = render_curation_page_v2("api-director")
    assert 'id="analyze"' in html
    assert 'id="findVideos"' in html
    assert 'id="findImages"' in html
    assert 'id="directorProviderV5"' in html
    assert 'id="generateDirectorV5"' in html
    assert 'id="refreshPlanV18"' in html
    assert "MANUAL / IMPORT" in html
    assert "AUTO" in html
    assert "GEMINI API" in html
    assert "GROQ API" in html
    assert "GENERATE PLAN" in html
    assert "REFRESH PLAN" in html
    assert "transcript only" in html
    assert "api('/ai/status')" in html
    assert "/director" in html


def test_director_status_surfaces_invalid_generated_plan_instead_of_completed():
    from backend.app.curation_ui_v2 import render_curation_page_v2

    html = render_curation_page_v2("invalid-plan-status")

    function = html[html.index("function syncDirectorControlsV5"):html.index("function runDirectorV5")]
    assert "state.data.editorial_error" in function
    assert function.index("state.data.editorial_error") < function.index("state.data.editorial_plan_ready")
    assert "Piano generato ma non utilizzabile" in function


def test_product_server_ai_status_never_exposes_api_key(monkeypatch, tmp_path):
    from backend.app.curation_server import create_app

    monkeypatch.setenv("GEMINI_API_KEY", "test-key-do-not-expose")
    monkeypatch.setenv("RAMBLA_DIRECTOR_MODEL", "gemini-3.8-flash")
    client = TestClient(create_app(
        project_root=tmp_path / "projects",
        allowed_media_roots=[tmp_path],
        probe_runner=lambda _: {"duration": 1, "fps": 25, "width": 1080, "height": 1920, "has_audio": False},
    ))

    response = client.get("/api/curation/ai/status")
    assert response.status_code == 200
    body = response.json()
    assert body["providers"]["gemini"]["configured"] is True
    assert body["providers"]["gemini"]["model"] == "gemini-3.8-flash"
    assert body["providers"]["gemini"]["source_video_sent_to_ai"] is False
    assert "groq" in body["providers"]
    assert "auto" in body["providers"]
    assert "test-key-do-not-expose" not in repr(body)


def test_api_first_product_keeps_curation_identity_without_v2_branding():
    from backend.app.curation_ui_v2 import render_curation_page_v2

    html = render_curation_page_v2("v5-brand")
    version = Path("RAMBLA_VERSION").read_text(encoding="utf-8").strip()
    assert f'<span class="brandProductV41">RMBL B ROLL</span><span class="releaseVersionV35">{version}</span>' in html
    assert "RAMBLA Curation V2" not in html
    assert "CURATION V2" not in html
    assert "Choose the editorial engine" in html
    assert "GEMINI API" in html
    assert "transcript only" in html


def test_product_ui_clears_stale_director_running_state_on_terminal_failure():
    from backend.app.curation_ui_v2 import render_curation_page_v2

    html = render_curation_page_v2("director-terminal")
    assert "window.ramblaRunTerminal" in html
    assert "stage_type==='director_api'" in html
    assert "Director ${String(r.status||'FAILED').toLowerCase()}" in html


def test_curation_ui_has_clean_console_copy_button():
    from backend.app.curation_ui_v2 import render_curation_page_v2

    html = render_curation_page_v2("copy-console")
    assert 'id="copyConsole"' in html
    assert "COPY CONSOLE" in html
    assert "function cleanConsoleText()" in html
    assert "$('copyConsole').onclick=copyConsole" in html


def test_copy_console_javascript_keeps_newlines_escaped_in_rendered_html():
    from backend.app.curation_ui_v2 import render_curation_page_v2

    html = render_curation_page_v2("copy-console-js")
    assert r"summary+'\n'+pre" in html
    assert r"rows.join('\n\n')" in html
    assert "summary+'\n'+pre" not in html


def test_product_ui_exposes_clickable_envato_search_shelf():
    from backend.app.curation_ui_v2 import render_curation_page_v2

    html = render_curation_page_v2("envato")
    assert "ENVATO ELEMENTS" in html
    assert 'id="envatoVideosV2"' in html
    assert "started.opened_in_chrome" in html
    assert "const external=window.open('about:blank','_blank')" not in html
    assert "if(provider==='envato'){window.open" not in html
    assert "session==='normal_chrome'" in html
    assert "socialReadyV5[provider]=true" not in html
    assert "official Envato download" in html
    assert 'id="envatoLoginV2"' in html
    assert "ENVATO · APRI ACCESSO" in html
    assert "socialLoginV2(\'envato\')" in html
    assert "Automatic public Envato catalog search" in html
    assert "LOGIN PROVIDER ESTERNI" in html
    assert "installEnvatoDownloadV29" in html
    assert "/envato/download/start" in html
    assert "SCARICA DA ENVATO" in html




