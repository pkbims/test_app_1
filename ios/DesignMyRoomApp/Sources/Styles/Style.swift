import Foundation

/// The style catalog — hard-coded per the client brief, shared with the backend by
/// convention rather than a contract field (`RenderCreate.style` is a bare string).
/// If the backend's accepted list ever differs, that's a cross-cutting question, not
/// something to guess at silently (see `../../ORCH-QUESTIONS.md`).
///
/// Ids and display names mirror `backend/app/render/prompt.py`'s `STYLES` dict
/// exactly, in the same declaration order. Grew 6 -> 18 per
/// `prompt_review/HANDOFF.md` §2, then 18 -> 62 for DecorAI name parity (commit
/// 6959d92) — `scandi` and `mid-century` picked up cosmetic display-name renames
/// in that second round ("Scandi" -> "Scandinavian", "Mid-Century" ->
/// "Mid-Century Modern"); their ids are unchanged. Twelve of the original 18 (plus
/// all 44 new ones minus a spot-checked handful) have no bundled sample-card image
/// yet as new styles land — `StyleImageResolver` already falls back to a tinted
/// placeholder for any id not in its `bundledStyleIds` set, so shipping the full
/// list doesn't wait on the art.
struct Style: Identifiable, Equatable {
    let id: String
    let displayName: String

    static let all: [Style] = [
        Style(id: "warm-minimal", displayName: "Warm Minimal"),
        Style(id: "scandi", displayName: "Scandinavian"),
        Style(id: "japandi", displayName: "Japandi"),
        Style(id: "modern-coastal", displayName: "Modern Coastal"),
        Style(id: "mid-century", displayName: "Mid-Century Modern"),
        Style(id: "industrial", displayName: "Industrial"),
        Style(id: "traditional", displayName: "Traditional"),
        Style(id: "art-deco", displayName: "Art Deco"),
        Style(id: "dark-academia", displayName: "Dark Academia"),
        Style(id: "maximalism", displayName: "Maximalism"),
        Style(id: "moroccan", displayName: "Moroccan"),
        Style(id: "cottagecore", displayName: "Cottagecore"),
        Style(id: "rustic-farmhouse", displayName: "Rustic Farmhouse"),
        Style(id: "mediterranean", displayName: "Mediterranean"),
        Style(id: "cyberpunk", displayName: "Cyberpunk"),
        Style(id: "memphis", displayName: "Memphis"),
        Style(id: "christmas", displayName: "Christmas"),
        Style(id: "valentines", displayName: "Valentine's Day"),
        Style(id: "minimalistic", displayName: "Minimalistic"),
        Style(id: "modern", displayName: "Modern"),
        Style(id: "transitional", displayName: "Transitional"),
        Style(id: "contemporary", displayName: "Contemporary"),
        Style(id: "japanese", displayName: "Japanese"),
        Style(id: "eclectic", displayName: "Eclectic"),
        Style(id: "rustic", displayName: "Rustic"),
        Style(id: "bohemian", displayName: "Bohemian"),
        Style(id: "farmhouse", displayName: "Farmhouse"),
        Style(id: "vintage", displayName: "Vintage"),
        Style(id: "victorian", displayName: "Victorian"),
        Style(id: "retro", displayName: "Retro"),
        Style(id: "zen", displayName: "Zen"),
        Style(id: "biophilic", displayName: "Biophilic"),
        Style(id: "solarpunk", displayName: "Solarpunk"),
        Style(id: "tropical", displayName: "Tropical"),
        Style(id: "parisian", displayName: "Parisian"),
        Style(id: "brutalist", displayName: "Brutalist"),
        Style(id: "vaporwave", displayName: "Vaporwave"),
        Style(id: "hollywood-regency", displayName: "Hollywood Regency"),
        Style(id: "art-nouveau", displayName: "Art Nouveau"),
        Style(id: "korean-hanok", displayName: "Korean Hanok"),
        Style(id: "southwestern", displayName: "Southwestern"),
        Style(id: "nordic-hygge", displayName: "Nordic Hygge"),
        Style(id: "baroque", displayName: "Baroque"),
        Style(id: "bauhaus", displayName: "Bauhaus"),
        Style(id: "futuristic", displayName: "Futuristic"),
        Style(id: "colonial", displayName: "Colonial"),
        Style(id: "tudor", displayName: "Tudor"),
        Style(id: "shaker", displayName: "Shaker"),
        Style(id: "rococo", displayName: "Rococo"),
        Style(id: "deconstructivism", displayName: "Deconstructivism"),
        Style(id: "wabi-sabi", displayName: "Wabi-Sabi"),
        Style(id: "organic-modern", displayName: "Organic Modern"),
        Style(id: "quiet-luxury", displayName: "Quiet Luxury"),
        Style(id: "french-country", displayName: "French Country"),
        Style(id: "english-country", displayName: "English Country"),
        Style(id: "neoclassical", displayName: "Neoclassical"),
        Style(id: "alpine-chalet", displayName: "Alpine Chalet"),
        Style(id: "hacienda", displayName: "Hacienda"),
        Style(id: "chinoiserie", displayName: "Chinoiserie"),
        Style(id: "shabby-chic", displayName: "Shabby Chic"),
        Style(id: "gothic", displayName: "Gothic"),
        Style(id: "steampunk", displayName: "Steampunk"),
    ]
}
