export type UserRole = "Editor" | "Creator";

export type ContentGoal = "Transformation" | "App Demo";

export type ScanStep =
  | "roleSelection"
  | "welcome"
  | "bpCreatorSelection"
  | "contentGoalSelection"
  | "peptideSelection"
  | "ratingSelection"
  | "recordingPrompt"
  | "problemsSelection"
  | "goalsSelection"
  | "photoCapture"
  | "scanning"
  | "results";

export type RatingGender = "Male" | "Female";

export type EditorRatingData = {
  gender: RatingGender;
  pslScore: number;
  currentRating: string;
  potentialRating: string;
};

export type Peptide = {
  id: string;
  commonName: string;
  chemicalName: string;
  category: string;
  subtitle: string;
  imageUrl?: string;
  protocol?: {
    displayMetric: string;
  };
  usageGuide?: {
    frequency?: string;
  };
};

export type CreatorAppState = {
  showMainApp: boolean;
  userName: string;
  userImageUrl: string | null;
  selectedPeptides: Peptide[];
  userRole: UserRole;
  editorRating: EditorRatingData | null;
  contentGoal: ContentGoal | null;
  contentFeature: string | null;
};
