import { EditorRatingData, Peptide, RatingGender } from "./types";

export const primaryGradient = "linear-gradient(90deg, #3A3A3A 0%, #181818 50%, #5C5C5C 100%)";

export const DEFAULT_EDITOR_RATING: EditorRatingData = {
  gender: "Male",
  pslScore: 5,
  currentRating: "MID MTN",
  potentialRating: "HIGH HTN",
};

const maleTiers = [
  "NONE",
  "Sub-3",
  "Sub-5",
  "LOW LTN",
  "MID LTN",
  "HIGH LTN",
  "LOW MTN",
  "MID MTN",
  "HIGH MTN",
  "LOW HTN",
  "MID HTN",
  "HIGH HTN",
  "LOW CHADLITE",
  "MID CHADLITE",
  "HIGH CHADLITE",
  "LOW CHAD",
  "MID CHAD",
  "HIGH CHAD",
  "LOW ADAM",
  "MID ADAM",
  "HIGH ADAM",
  "TRUE ADAM",
  "MAXIMIZED",
];

const femaleTiers = [
  "NONE",
  "Sub-3",
  "Sub-5",
  "LOW LTB",
  "MID LTB",
  "HIGH LTB",
  "LOW MTB",
  "MID MTB",
  "HIGH MTB",
  "LOW HTB",
  "MID HTB",
  "HIGH HTB",
  "LOW STACYLITE",
  "MID STACYLITE",
  "HIGH STACYLITE",
  "LOW STACY",
  "MID STACY",
  "HIGH STACY",
  "LOW EVE",
  "MID EVE",
  "HIGH EVE",
  "TRUE EVE",
  "MAXIMIZED",
];

export function tiersForGender(gender: RatingGender): string[] {
  return gender === "Male" ? maleTiers : femaleTiers;
}

export function tierProgress(rating: string, gender: RatingGender): number {
  const tiers = tiersForGender(gender);
  const index = tiers.indexOf(rating);
  if (index < 0) {
    return 0.5;
  }
  return index / Math.max(tiers.length - 1, 1);
}

export const contentGoals = [
  {
    value: "Transformation" as const,
    description: "Full scan flow with dramatic before/after results.",
  },
  {
    value: "App Demo" as const,
    description: "Show off the full app with your custom peptide cycle.",
  },
];

export const problemsBySection = {
  Physique: [
    ["High Body Fat", "⚖️"],
    ["Too Skinny / Low Mass", "🦴"],
    ["Weak Frame Structure", "🧱"],
    ["Slow Muscle Growth", "🐌"],
    ["Low Strength Output", "🪫"],
  ],
  "Face Aesthetics": [
    ["Soft or Undefined Jawline", "😐"],
    ["Tired / Sunken Eyes", "👁️"],
    ["Facial Asymmetry", "🎭"],
    ["Poor Facial Development", "📉"],
  ],
  Recovery: [
    ["Slow Recovery", "😴"],
    ["Joint or Tendon Weakness", "🦵"],
    ["Brain Fog", "🧠"],
    ["Low Daily Energy", "⚡"],
  ],
  "Skin / Hair": [
    ["Poor Skin Quality", "🧴"],
    ["Acne / Inflammation", "🌫️"],
    ["Hair Thinning", "🧑‍🦲"],
    ["Slow Hair Growth", "🧬"],
  ],
  Health: [
    ["Aging Fast", "⏳"],
    ["Hormonal Imbalance", "🧪"],
  ],
} as const;

export const goalsOptions: Array<[string, string]> = [
  ["Get Taller", "📏"],
  ["Gain Muscle", "💪"],
  ["Lose Fat", "🔥"],
  ["More Facial Bone Mass", "🗿"],
  ["Higher IQ / Focus", "🧠"],
  ["Clear Skin / Hair", "✨"],
  ["Injury Recovery", "🦴"],
];

export const peptides: Peptide[] = [
  { id: "semaglutide", commonName: "Semaglutide", chemicalName: "GLP-1 Agonist", category: "Fat Loss", subtitle: "GLP-1 Receptor Agonist", imageUrl: "https://firebasestorage.googleapis.com/v0/b/hardmaxx-prod.firebasestorage.app/o/app%20images%2Fpeptides%2Fsemaglutide.webp?alt=media&token=9eb4e654-fceb-472e-b073-eae8455d7094", protocol: { displayMetric: "0.25mg" }, usageGuide: { frequency: "Weekly" } },
  { id: "tirzepatide", commonName: "Tirzepatide", chemicalName: "GLP-1 / GIP Agonist", category: "Fat Loss", subtitle: "Dual GIP/GLP-1 Agonist", imageUrl: "https://firebasestorage.googleapis.com/v0/b/hardmaxx-prod.firebasestorage.app/o/app%20images%2Fpeptides%2Ftirzepatide.webp?alt=media&token=75825e2f-a0a3-4a49-bef5-9ba28ac70f0b", protocol: { displayMetric: "2.5mg" }, usageGuide: { frequency: "Weekly" } },
  { id: "aod9604", commonName: "AOD-9604", chemicalName: "HGH Fragment", category: "Fat Loss", subtitle: "Anti-Obesity Drug Fragment", imageUrl: "https://firebasestorage.googleapis.com/v0/b/hardmaxx-prod.firebasestorage.app/o/app%20images%2Fpeptides%2FAOD9604.webp?alt=media&token=858e08c4-fe69-46fc-ae19-ab1797ac34f1", protocol: { displayMetric: "300mcg" }, usageGuide: { frequency: "Daily" } },
  { id: "motsc", commonName: "MOTS-c", chemicalName: "Mitochondrial-Derived Peptide", category: "Fat Loss", subtitle: "Mitochondrial Peptide", imageUrl: "https://firebasestorage.googleapis.com/v0/b/hardmaxx-prod.firebasestorage.app/o/app%20images%2Fpeptides%2Fmotsc.webp?alt=media&token=4186dddc-e7bc-40c0-9b51-010f2d88849c", protocol: { displayMetric: "5mg" }, usageGuide: { frequency: "Weekly" } },
  { id: "mk677", commonName: "MK-677", chemicalName: "Ibutamoren", category: "Muscle", subtitle: "Growth Hormone Secretagogue", imageUrl: "https://firebasestorage.googleapis.com/v0/b/hardmaxx-prod.firebasestorage.app/o/app%20images%2Fpeptides%2FMK-677.webp?alt=media&token=ed51eac9-301a-44f7-b783-bab34a04a9f5", protocol: { displayMetric: "15mg" }, usageGuide: { frequency: "Daily" } },
  { id: "rad140", commonName: "RAD140", chemicalName: "Testolone", category: "Muscle", subtitle: "Selective Androgen Modulator", imageUrl: "https://firebasestorage.googleapis.com/v0/b/hardmaxx-prod.firebasestorage.app/o/app%20images%2Fpeptides%2Frad140.webp?alt=media&token=88ba1de4-f55b-4867-b1f6-be8256714a9e", protocol: { displayMetric: "10mg" }, usageGuide: { frequency: "Daily" } },
  { id: "cjc1295", commonName: "CJC-1295", chemicalName: "Mod GRF 1-29", category: "Muscle", subtitle: "Growth Hormone Releasing Hormone", imageUrl: "https://firebasestorage.googleapis.com/v0/b/hardmaxx-prod.firebasestorage.app/o/app%20images%2Fpeptides%2FCJC-1295.webp?alt=media&token=8238eb30-f13e-47e5-9c5f-a30855443851", protocol: { displayMetric: "2mg" }, usageGuide: { frequency: "Weekly" } },
  { id: "ipamorelin", commonName: "Ipamorelin", chemicalName: "Ipamorelin", category: "Muscle", subtitle: "Growth Hormone Releasing Peptide", imageUrl: "https://firebasestorage.googleapis.com/v0/b/hardmaxx-prod.firebasestorage.app/o/app%20images%2Fpeptides%2Fipamorelin.webp?alt=media&token=36144cbb-6ef9-4605-a68d-88d2c3ecf7a7", protocol: { displayMetric: "200mcg" }, usageGuide: { frequency: "Daily" } },
  { id: "bpc157", commonName: "BPC-157 (Inject)", chemicalName: "Body Protection Compound", category: "Recovery", subtitle: "Body Protection Compound", imageUrl: "https://firebasestorage.googleapis.com/v0/b/hardmaxx-prod.firebasestorage.app/o/app%20images%2Fpeptides%2FBPC-157.webp?alt=media&token=4a0d7408-6c91-4dd1-b55a-b4daec6a5f33", protocol: { displayMetric: "500mcg" }, usageGuide: { frequency: "Daily" } },
  { id: "tb500", commonName: "TB-500", chemicalName: "Thymosin Beta-4", category: "Recovery", subtitle: "Recovery Peptide", imageUrl: "https://firebasestorage.googleapis.com/v0/b/hardmaxx-prod.firebasestorage.app/o/app%20images%2Fpeptides%2FTB500.webp?alt=media", protocol: { displayMetric: "2mg" }, usageGuide: { frequency: "Weekly" } },
  { id: "ss31", commonName: "SS-31", chemicalName: "Elamipretide", category: "Recovery", subtitle: "Mitochondrial Peptide", imageUrl: "https://firebasestorage.googleapis.com/v0/b/hardmaxx-prod.firebasestorage.app/o/app%20images%2Fpeptides%2Fss31.webp?alt=media&token=a79541db-3935-479a-9c97-9003aaf603dc", protocol: { displayMetric: "10mg" }, usageGuide: { frequency: "Weekly" } },
  { id: "pt141", commonName: "PT-141", chemicalName: "Bremelanotide", category: "Recovery", subtitle: "Melanocortin Receptor Agonist", imageUrl: "https://firebasestorage.googleapis.com/v0/b/hardmaxx-prod.firebasestorage.app/o/app%20images%2Fpeptides%2Fpt141.webp?alt=media&token=447f5edc-08eb-410f-8890-aef6a45af771", protocol: { displayMetric: "1mg" }, usageGuide: { frequency: "As needed" } },
  { id: "ghkcu", commonName: "GHK-Cu (Inject)", chemicalName: "Copper Peptide", category: "Skin", subtitle: "Copper Peptide Complex", imageUrl: "https://firebasestorage.googleapis.com/v0/b/hardmaxx-prod.firebasestorage.app/o/app%20images%2Fpeptides%2FGHK-Cu.webp?alt=media&token=46a040c4-249c-4bc5-9704-19adfd173df8", protocol: { displayMetric: "2mg" }, usageGuide: { frequency: "Weekly" } },
  { id: "ghkcu_topical", commonName: "GHK-Cu (Topical)", chemicalName: "Copper Peptide Serum", category: "Skin", subtitle: "Topical Copper Peptide", imageUrl: "https://firebasestorage.googleapis.com/v0/b/hardmaxx-prod.firebasestorage.app/o/app%20images%2Fpeptides%2FGHK-Cu_topical.webp?alt=media&token=a121be54-b94b-490f-89e2-6e55365e43ee", protocol: { displayMetric: "2 pumps" }, usageGuide: { frequency: "Daily" } },
  { id: "melanotan2", commonName: "Melanotan 2", chemicalName: "Melanotan II", category: "Aesthetics", subtitle: "Melanocortin Receptor Agonist", imageUrl: "https://firebasestorage.googleapis.com/v0/b/hardmaxx-prod.firebasestorage.app/o/app%20images%2Fpeptides%2Fmelanotan%20II.webp?alt=media&token=4b30c86c-8834-4866-ae3f-7c08d1cfa669", protocol: { displayMetric: "250mcg" }, usageGuide: { frequency: "Daily" } },
  { id: "semax", commonName: "Semax", chemicalName: "Semax", category: "Nootropic", subtitle: "Nootropic Neuropeptide", imageUrl: "https://firebasestorage.googleapis.com/v0/b/hardmaxx-prod.firebasestorage.app/o/app%20images%2Fpeptides%2Fsemax.webp?alt=media&token=d5614b59-e642-454e-8abb-958af2daff87", protocol: { displayMetric: "300mcg" }, usageGuide: { frequency: "Daily" } },
  { id: "selank", commonName: "Selank", chemicalName: "Selank", category: "Cognitive", subtitle: "Anxiolytic Neuropeptide", imageUrl: "https://firebasestorage.googleapis.com/v0/b/hardmaxx-prod.firebasestorage.app/o/app%20images%2Fpeptides%2Fselank.webp?alt=media", protocol: { displayMetric: "300mcg" }, usageGuide: { frequency: "Daily" } },
  { id: "cerebrolysin", commonName: "Cerebrolysin", chemicalName: "Cerebrolysin", category: "Nootropic", subtitle: "Neurotrophic Peptide Mixture", imageUrl: "https://firebasestorage.googleapis.com/v0/b/hardmaxx-prod.firebasestorage.app/o/app%20images%2Fpeptides%2Fcerebrolysin.webp?alt=media&token=fb9ba9c7-970c-4ba5-874f-e27c600decb2", protocol: { displayMetric: "5ml" }, usageGuide: { frequency: "Weekly" } },
  { id: "rapamycin", commonName: "Rapamycin", chemicalName: "Sirolimus", category: "Longevity", subtitle: "mTOR Inhibitor", imageUrl: "https://firebasestorage.googleapis.com/v0/b/hardmaxx-prod.firebasestorage.app/o/app%20images%2Fpeptides%2Frapamycin.webp?alt=media&token=cb3c6410-4848-46c5-b956-239a2863cb0a", protocol: { displayMetric: "6mg" }, usageGuide: { frequency: "Weekly" } },
  { id: "epitalon", commonName: "Epitalon", chemicalName: "Epithalon", category: "Longevity", subtitle: "Telomerase Activator", imageUrl: "https://firebasestorage.googleapis.com/v0/b/hardmaxx-prod.firebasestorage.app/o/app%20images%2Fpeptides%2Fepitalon.webp?alt=media&token=3954434f-20e3-4951-8cce-dfeef0107c3e", protocol: { displayMetric: "10mg" }, usageGuide: { frequency: "Daily" } },
  { id: "nad_plus", commonName: "NAD+", chemicalName: "Nicotinamide Adenine Dinucleotide", category: "Longevity", subtitle: "Cellular Coenzyme", imageUrl: "https://firebasestorage.googleapis.com/v0/b/hardmaxx-prod.firebasestorage.app/o/app%20images%2Fpeptides%2Fnad_plus.png?alt=media", protocol: { displayMetric: "250mg" }, usageGuide: { frequency: "Weekly" } },
  { id: "glutathione", commonName: "L-Glutathione", chemicalName: "Master Antioxidant", category: "Antioxidant", subtitle: "Master Antioxidant", imageUrl: "https://firebasestorage.googleapis.com/v0/b/hardmaxx-prod.firebasestorage.app/o/app%20images%2Fpeptides%2Fglutathione.png?alt=media", protocol: { displayMetric: "600mg" }, usageGuide: { frequency: "Weekly" } },
  { id: "hcg", commonName: "HCG", chemicalName: "Human Chorionic Gonadotropin", category: "Hormone", subtitle: "Gonadotropin Hormone", imageUrl: "https://firebasestorage.googleapis.com/v0/b/hardmaxx-prod.firebasestorage.app/o/app%20images%2Fpeptides%2Fhcg.png?alt=media", protocol: { displayMetric: "500iu" }, usageGuide: { frequency: "Twice weekly" } },
  { id: "tadalafil", commonName: "Tadalafil", chemicalName: "PDE5 Inhibitor", category: "Performance", subtitle: "PDE5 Inhibitor", imageUrl: "https://firebasestorage.googleapis.com/v0/b/hardmaxx-prod.firebasestorage.app/o/app%20images%2Fpeptides%2Ftadalafil.png?alt=media", protocol: { displayMetric: "5mg" }, usageGuide: { frequency: "Daily" } },
  { id: "slupp332", commonName: "SLU-PP-332", chemicalName: "ERR Agonist", category: "Performance", subtitle: "ERR Agonist", imageUrl: "https://firebasestorage.googleapis.com/v0/b/hardmaxx-prod.firebasestorage.app/o/app%20images%2Fpeptides%2Fslupp332.png?alt=media", protocol: { displayMetric: "20mg" }, usageGuide: { frequency: "Daily" } },
];

export function allPeptideCategories(): string[] {
  return ["All", ...Array.from(new Set(peptides.map((peptide) => peptide.category))).sort((a, b) => a.localeCompare(b))];
}

export function peptidesByIds(ids: Set<string>): Peptide[] {
  return peptides.filter((peptide) => ids.has(peptide.id));
}
