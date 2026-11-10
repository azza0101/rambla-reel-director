import zipfile
from pathlib import Path


def test_effect_preserves_paper_motion_and_shadow_controls():
    import re
    assert (Path(__file__).resolve().parents[2]/'backend/app/kura_text_effect.py').is_file()
    from backend.app.kura_text_effect import convert_title_to_effect
    from backend.app.kura_text_effect import source_title_setting
    source=source_title_setting()
    effect=convert_title_to_effect(source)
    for name in ('Color_Back_cColorRed','Texture_Brightness','Texture_Contrast',
                 'Wiggle_Posterize','Wiggle_X_Strength','Wiggle_Y_Strength',
                 'Wiggle_Angle_Strength','DropShadow2_shadowStrength',
                 'DropShadow2_shadowAngle','DropShadow2_ShadowDistance','DropShadow2_shadowBlur'):
        assert name in source and name in effect
    assert 'KURA_Input_AutoDomain = AutoDomain' in effect
    assert 'SourceOp = "KURA_Input_AutoDomain"' in effect
    assert 'MainInput1 = InstanceInput' in effect
    assert 'Template = PipeRouter' in effect
    assert 'Template_StyledText = InstanceInput' not in effect
    assert 'setting:/paper.jpg' in effect
    entries=re.findall(r'(\w+)\s*=\s*InstanceInput\s*\{([^{}]*)\}',source,re.S)
    graphics={name for name,body in entries if 'SourceOp = "Template"' not in body}
    assert len(graphics)==19
    assert all(re.search(r'\b'+re.escape(name)+r'\s*=\s*InstanceInput',effect) for name in graphics)


def test_effect_package_contains_its_settings_and_all_visual_assets(tmp_path):
    assert (Path(__file__).resolve().parents[2]/'backend/app/kura_text_effect.py').is_file()
    from backend.app.kura_text_effect import build_effect_package
    target=tmp_path/'effect.drfx'
    build_effect_package(target)
    prefix='Edit/Effects/KURA_Paper_Text_Optimized/'
    with zipfile.ZipFile(target) as z:
        assert prefix+'KURA_Paper_Text_Optimized.setting' in z.namelist()
        assert prefix+'paper.jpg' in z.namelist()
        assert prefix+'Center/LLmotion_C_001.png' in z.namelist()
        assert prefix+'Rect/LLmotion_Rect_001.png' in z.namelist()


def test_install_bundle_includes_platform_installers_and_effect(tmp_path):
    from backend.app.kura_text_effect import build_effect_install_bundle
    bundle=tmp_path/'bundle.zip'
    build_effect_install_bundle(bundle)
    with zipfile.ZipFile(bundle) as z:
        assert 'KURA_Paper_Text_Optimized.drfx' in z.namelist()
        assert 'Installa KURA Windows.cmd' in z.namelist()
        assert 'Installa KURA Windows.ps1' in z.namelist()
        assert 'Installa KURA Mac.command' in z.namelist()
        ps=z.read('Installa KURA Windows.ps1').decode('utf8')
        assert 'Edit\\Effects\\KURA_Paper_Text_Optimized' in ps
        assert 'KURA_paper_title_v9_STANDALONE_FIXED.drfx' not in ps


def test_windows_installer_installs_effect_without_changing_original_title(tmp_path):
    import os
    import subprocess
    import pytest
    from backend.app.kura_text_effect import build_effect_install_bundle
    if os.name!='nt':pytest.skip('Windows installer')
    bundle=tmp_path/'bundle.zip';build_effect_install_bundle(bundle)
    install=tmp_path/'install';install.mkdir()
    with zipfile.ZipFile(bundle) as z:z.extractall(install)
    root=tmp_path/'appdata'/'Blackmagic Design'/'DaVinci Resolve'/'Support'/'Fusion'/'Templates'
    old=root/'Edit'/'Titles'/'KURA_paper_title_v9'/'KURA_paper_title_v9.setting'
    old.parent.mkdir(parents=True);old.write_bytes(b'existing-original')
    cmd=['powershell.exe','-NoProfile','-ExecutionPolicy','Bypass','-File',str(install/'Installa KURA Windows.ps1')]
    env=dict(os.environ,APPDATA=str(tmp_path/'appdata'))
    for _ in range(2):
        result=subprocess.run(cmd,env=env,capture_output=True,text=True,timeout=30)
        assert result.returncode==0,result.stderr
    effect=root/'Edit'/'Effects'/'KURA_Paper_Text_Optimized'/'KURA_Paper_Text_Optimized.setting'
    assert effect.is_file()
    assert old.read_bytes()==b'existing-original'
