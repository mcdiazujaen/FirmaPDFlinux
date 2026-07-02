import os
import sys
import json

def _get_config_dir():
    # Si la aplicación está empaquetada (PyInstaller), guardamos en la carpeta personal del usuario
    if getattr(sys, 'frozen', False):
        config_dir = os.path.expanduser("~/.firmapdf")
        os.makedirs(config_dir, exist_ok=True)
        return config_dir
    else:
        # En modo desarrollo, guardamos en la raíz del proyecto
        return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

CONFIG_DIR = _get_config_dir()
SETTINGS_FILE = os.path.join(CONFIG_DIR, "settings.json")
PROFILES_FILE = os.path.join(CONFIG_DIR, "signature_profiles.json")

DEFAULT_SETTINGS = {
    "autofirma_path": "",
    "theme": "light",
    "active_profile": "Default"
}

DEFAULT_PROFILE = {
    "name": "Default",
    "cert_filter": "",
    "rubric_image_path": "",
    "signature_text": "Firmado digitalmente por $$SUBJECTCN$$ el $$SIGNDATE=dd/MM/yyyy HH:mm:ss$$",
    "signature_font": "Helvetica",
    "signature_font_size": 0,   # 0 = automático
    "rubric_layout": "side_by_side",  # "side_by_side" | "background"
    "store": "auto",            # "auto" | "windows" | "mac" | "mozilla" | "pkcs12"
    "store_pkcs12_path": ""     # ruta al fichero .p12/.pfx (solo cuando store == "pkcs12")
}

def load_settings():
    if not os.path.exists(SETTINGS_FILE):
        return DEFAULT_SETTINGS.copy()
    try:
        with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
            settings = json.load(f)
            # Migrar claves antiguas al perfil por defecto si existen
            _migrate_legacy_settings(settings)
            # Asegurar que todas las llaves por defecto existen
            for key, val in DEFAULT_SETTINGS.items():
                if key not in settings:
                    settings[key] = val
            return settings
    except Exception as e:
        print(f"Error cargando configuración: {e}")
        return DEFAULT_SETTINGS.copy()

def _migrate_legacy_settings(settings):
    """Migra claves antiguas (cert_filter, rubric_image_path, signature_text) a perfiles."""
    legacy_keys = ["cert_filter", "rubric_image_path", "signature_text"]
    has_legacy = any(k in settings for k in legacy_keys)
    if not has_legacy:
        return

    # Cargar perfiles existentes
    profiles = load_profiles()
    # Si ya existe el perfil "Default (migrado)" no repetir
    migrated_name = "Default (migrado)"
    if not any(p["name"] == migrated_name for p in profiles):
        new_profile = DEFAULT_PROFILE.copy()
        new_profile["name"] = migrated_name
        for k in legacy_keys:
            if k in settings:
                new_profile[k] = settings[k]
        profiles.append(new_profile)
        save_profiles(profiles)
        settings["active_profile"] = migrated_name

    # Eliminar las claves antiguas del settings global
    for k in legacy_keys:
        settings.pop(k, None)

def save_settings(settings):
    try:
        with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
            json.dump(settings, f, indent=4, ensure_ascii=False)
        return True
    except Exception as e:
        print(f"Error guardando configuración: {e}")
        return False

def load_profiles():
    """Carga la lista de perfiles de firma desde el archivo JSON de perfiles."""
    if not os.path.exists(PROFILES_FILE):
        return [DEFAULT_PROFILE.copy()]
    try:
        with open(PROFILES_FILE, "r", encoding="utf-8") as f:
            profiles = json.load(f)
            if not isinstance(profiles, list) or len(profiles) == 0:
                return [DEFAULT_PROFILE.copy()]
            # Asegurar que cada perfil tiene todas las claves por defecto
            for profile in profiles:
                for key, val in DEFAULT_PROFILE.items():
                    if key not in profile:
                        profile[key] = val
            return profiles
    except Exception as e:
        print(f"Error cargando perfiles: {e}")
        return [DEFAULT_PROFILE.copy()]

def save_profiles(profiles):
    """Guarda la lista de perfiles de firma en el archivo JSON de perfiles."""
    try:
        with open(PROFILES_FILE, "w", encoding="utf-8") as f:
            json.dump(profiles, f, indent=4, ensure_ascii=False)
        return True
    except Exception as e:
        print(f"Error guardando perfiles: {e}")
        return False

def get_active_profile(settings, profiles):
    """Devuelve el perfil activo según la configuración, o el primero disponible."""
    active_name = settings.get("active_profile", "")
    for p in profiles:
        if p["name"] == active_name:
            return p
    return profiles[0] if profiles else DEFAULT_PROFILE.copy()
