"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import {
  allPeptideCategories,
  contentGoals,
  DEFAULT_EDITOR_RATING,
  goalsOptions,
  peptides,
  peptidesByIds,
  primaryGradient,
  problemsBySection,
  tierProgress,
  tiersForGender,
} from "./data";
import { useViewportRecorder } from "./useViewportRecorder";
import { ContentGoal, CreatorAppState, EditorRatingData, Peptide, ScanStep, UserRole } from "./types";

const loadingBullets = [
  "Analyzing facial structure",
  "Matching peptide treatments",
  "Optimizing dosage protocol",
  "Generating your results",
];

const defaultAppState: CreatorAppState = {
  showMainApp: false,
  userName: "",
  userImageUrl: null,
  selectedPeptides: [],
  userRole: "Creator",
  editorRating: null,
  contentGoal: null,
  contentFeature: null,
};

function cn(...values: Array<string | false | null | undefined>) {
  return values.filter(Boolean).join(" ");
}

export function CreatorWebApp() {
  const phoneViewportRef = useRef<HTMLDivElement>(null);
  const { status, error: recorderError, supportsRegionCrop, startRecording, stopRecording } = useViewportRecorder(phoneViewportRef);

  const [appState, setAppState] = useState<CreatorAppState>(defaultAppState);
  const [currentStep, setCurrentStep] = useState<ScanStep>("roleSelection");
  const [userRole, setUserRole] = useState<UserRole>("Creator");
  const [isBPCreator, setIsBPCreator] = useState(false);
  const [userName, setUserName] = useState("");
  const [selectedContentGoal, setSelectedContentGoal] = useState<ContentGoal | null>(null);
  const [selectedPeptideIds, setSelectedPeptideIds] = useState<Set<string>>(new Set());
  const [selectedProblems, setSelectedProblems] = useState<Set<string>>(new Set());
  const [selectedGoals, setSelectedGoals] = useState<Set<string>>(new Set());
  const [capturedImageUrl, setCapturedImageUrl] = useState<string | null>(null);
  const [editorRating, setEditorRating] = useState<EditorRatingData>(DEFAULT_EDITOR_RATING);
  const [matchedPeptides, setMatchedPeptides] = useState<Peptide[]>([]);
  const [mainTab, setMainTab] = useState(0);

  useEffect(() => {
    return () => {
      if (capturedImageUrl?.startsWith("blob:")) {
        URL.revokeObjectURL(capturedImageUrl);
      }
    };
  }, [capturedImageUrl]);

  const effectiveRole: UserRole = isBPCreator && selectedContentGoal === "Transformation" ? "Editor" : userRole;

  const enterMainApp = (nextPeptides: Peptide[], goal: ContentGoal | null, rating: EditorRatingData | null) => {
    setAppState({
      showMainApp: true,
      userName: userName.trim() || "Creator",
      userImageUrl: capturedImageUrl,
      selectedPeptides: nextPeptides,
      userRole,
      editorRating: rating,
      contentGoal: goal,
      contentFeature: null,
    });
  };

  const resetFlow = () => {
    setCurrentStep("roleSelection");
    setUserRole("Creator");
    setIsBPCreator(false);
    setUserName("");
    setSelectedContentGoal(null);
    setSelectedPeptideIds(new Set());
    setSelectedProblems(new Set());
    setSelectedGoals(new Set());
    setEditorRating(DEFAULT_EDITOR_RATING);
    setMatchedPeptides([]);
    setAppState(defaultAppState);
    if (capturedImageUrl?.startsWith("blob:")) {
      URL.revokeObjectURL(capturedImageUrl);
    }
    setCapturedImageUrl(null);
    setMainTab(0);
  };

  const proceedFromPeptides = () => {
    const picked = peptidesByIds(selectedPeptideIds);
    setMatchedPeptides(picked);

    if (userRole === "Editor") {
      setCurrentStep("ratingSelection");
      return;
    }

    if (selectedContentGoal === "Transformation") {
      if (isBPCreator) {
        setCurrentStep("ratingSelection");
      } else {
        setCurrentStep("recordingPrompt");
      }
      return;
    }

    if (selectedContentGoal === "App Demo") {
      enterMainApp(picked, "App Demo", null);
      return;
    }

    setCurrentStep("recordingPrompt");
  };

  const shellStatus =
    status === "recording" ? "Recording" : status === "stopping" ? "Finishing file" : "Ready";

  return (
    <div className="creator-shell">
      <aside className="creator-controls">
        <h1>Creator Web Staging</h1>
        <p>Desktop shell with a fixed iPhone viewport. Recording controls stay outside the phone frame.</p>
        <div className="control-card">
          <div className="control-row">
            <span>Status</span>
            <strong>{shellStatus}</strong>
          </div>
          <div className="control-row">
            <span>Region crop</span>
            <strong>{supportsRegionCrop ? "Enabled" : "Browser fallback"}</strong>
          </div>
          <div className="control-actions">
            <button type="button" className="shell-button solid" onClick={startRecording} disabled={status !== "idle"}>
              Start Recording
            </button>
            <button type="button" className="shell-button" onClick={stopRecording} disabled={status !== "recording"}>
              Stop + Download
            </button>
          </div>
          {recorderError ? <p className="control-error">{recorderError}</p> : null}
          <p className="control-help">Choose the current tab/window when prompted. If crop is unsupported, recording includes surrounding area.</p>
        </div>
        <button type="button" className="shell-button reset" onClick={resetFlow}>
          Reset Flow
        </button>
      </aside>

      <main className="phone-stage">
        <div className="phone-frame">
          <div className="phone-notch" />
          <div className="phone-viewport" ref={phoneViewportRef}>
            {appState.showMainApp ? (
              <MainAppView appState={appState} mainTab={mainTab} setMainTab={setMainTab} onRestart={resetFlow} />
            ) : (
              <FlowView
                currentStep={currentStep}
                userRole={userRole}
                setUserRole={setUserRole}
                isBPCreator={isBPCreator}
                setIsBPCreator={setIsBPCreator}
                userName={userName}
                setUserName={setUserName}
                selectedContentGoal={selectedContentGoal}
                setSelectedContentGoal={setSelectedContentGoal}
                selectedPeptideIds={selectedPeptideIds}
                setSelectedPeptideIds={setSelectedPeptideIds}
                selectedProblems={selectedProblems}
                setSelectedProblems={setSelectedProblems}
                selectedGoals={selectedGoals}
                setSelectedGoals={setSelectedGoals}
                capturedImageUrl={capturedImageUrl}
                setCapturedImageUrl={setCapturedImageUrl}
                editorRating={editorRating}
                setEditorRating={setEditorRating}
                matchedPeptides={matchedPeptides}
                setMatchedPeptides={setMatchedPeptides}
                effectiveRole={effectiveRole}
                setCurrentStep={setCurrentStep}
                proceedFromPeptides={proceedFromPeptides}
                enterMainApp={enterMainApp}
                resetFlow={resetFlow}
              />
            )}
          </div>
        </div>
      </main>
    </div>
  );
}

type FlowViewProps = {
  currentStep: ScanStep;
  userRole: UserRole;
  setUserRole: (role: UserRole) => void;
  isBPCreator: boolean;
  setIsBPCreator: (next: boolean) => void;
  userName: string;
  setUserName: (name: string) => void;
  selectedContentGoal: ContentGoal | null;
  setSelectedContentGoal: (goal: ContentGoal) => void;
  selectedPeptideIds: Set<string>;
  setSelectedPeptideIds: (ids: Set<string>) => void;
  selectedProblems: Set<string>;
  setSelectedProblems: (items: Set<string>) => void;
  selectedGoals: Set<string>;
  setSelectedGoals: (items: Set<string>) => void;
  capturedImageUrl: string | null;
  setCapturedImageUrl: (url: string | null) => void;
  editorRating: EditorRatingData;
  setEditorRating: (rating: EditorRatingData) => void;
  matchedPeptides: Peptide[];
  setMatchedPeptides: (items: Peptide[]) => void;
  effectiveRole: UserRole;
  setCurrentStep: (step: ScanStep) => void;
  proceedFromPeptides: () => void;
  enterMainApp: (peptides: Peptide[], goal: ContentGoal | null, rating: EditorRatingData | null) => void;
  resetFlow: () => void;
};

function FlowView(props: FlowViewProps) {
  const {
    currentStep,
    userRole,
    setUserRole,
    isBPCreator,
    setIsBPCreator,
    userName,
    setUserName,
    selectedContentGoal,
    setSelectedContentGoal,
    selectedPeptideIds,
    setSelectedPeptideIds,
    selectedProblems,
    setSelectedProblems,
    selectedGoals,
    setSelectedGoals,
    capturedImageUrl,
    setCapturedImageUrl,
    editorRating,
    setEditorRating,
    matchedPeptides,
    setMatchedPeptides,
    effectiveRole,
    setCurrentStep,
    proceedFromPeptides,
    enterMainApp,
    resetFlow,
  } = props;

  if (currentStep === "roleSelection") {
    return (
      <CardScreen title="REGEN" subtitle="#1 Science Based Peptide Transformation App">
        <p className="screen-prompt">Who is using this app?</p>
        <div className="stack-12">
          <button
            type="button"
            className="role-button"
            onClick={() => {
              setUserRole("Editor");
              setCurrentStep("peptideSelection");
            }}
          >
            <span className="role-icon">✏️</span>
            <span>Editor</span>
            <span className="chevron">›</span>
          </button>
          <button
            type="button"
            className="role-button"
            onClick={() => {
              setUserRole("Creator");
              setCurrentStep("bpCreatorSelection");
            }}
          >
            <span className="role-icon">🎬</span>
            <span>Creator</span>
            <span className="chevron">›</span>
          </button>
        </div>
      </CardScreen>
    );
  }

  if (currentStep === "bpCreatorSelection") {
    return (
      <CardScreen title="REGEN" subtitle="Are you a BP creator?">
        <div className="stack-12">
          <button
            type="button"
            className="primary-pill"
            onClick={() => {
              setIsBPCreator(true);
              setCurrentStep("contentGoalSelection");
            }}
          >
            YES
          </button>
          <button
            type="button"
            className="secondary-pill"
            onClick={() => {
              setIsBPCreator(false);
              setCurrentStep("welcome");
            }}
          >
            NO
          </button>
        </div>
      </CardScreen>
    );
  }

  if (currentStep === "welcome") {
    return (
      <CardScreen title="REGEN" subtitle={userRole === "Editor" ? "type in the name of the\ncharacter you are editing" : "enter your name to\nget started"}>
        <input
          className="name-input"
          placeholder={userRole === "Editor" ? "character name" : "your name"}
          value={userName}
          onChange={(event) => setUserName(event.target.value)}
          onKeyDown={(event) => {
            if (event.key === "Enter" && userName.trim()) {
              setCurrentStep("contentGoalSelection");
            }
          }}
        />
        <p className={cn("hint", userName.trim() && "visible")}>press return to continue</p>
      </CardScreen>
    );
  }

  if (currentStep === "contentGoalSelection") {
    return (
      <div className="screen white">
        <div className="top-title">Choose video type</div>
        <div className="stack-12 padded-24">
          {contentGoals.map((goal) => (
            <button
              key={goal.value}
              type="button"
              className={cn("goal-card", selectedContentGoal === goal.value && "selected")}
              onClick={() => {
                setSelectedContentGoal(goal.value);
                setCurrentStep("peptideSelection");
              }}
            >
              <div>
                <h4>{goal.value}</h4>
                <p>{goal.description}</p>
              </div>
              <span className="chevron">›</span>
            </button>
          ))}
        </div>
      </div>
    );
  }

  if (currentStep === "peptideSelection") {
    return (
      <PeptideSelectionScreen
        selectedIds={selectedPeptideIds}
        setSelectedIds={setSelectedPeptideIds}
        maxSelections={effectiveRole === "Editor" ? 2 : 3}
        onContinue={proceedFromPeptides}
      />
    );
  }

  if (currentStep === "ratingSelection") {
    return <RatingScreen rating={editorRating} onChange={setEditorRating} onContinue={() => setCurrentStep("recordingPrompt")} />;
  }

  if (currentStep === "recordingPrompt") {
    return (
      <CardScreen title="REGEN" subtitle="Enable Screen Recording before proceeding to capture your results.">
        <p className="body-copy">Open Control Center, then tap the Screen Recording button.</p>
        <button type="button" className="primary-pill" onClick={() => setCurrentStep("problemsSelection")}>
          CONTINUE →
        </button>
      </CardScreen>
    );
  }

  if (currentStep === "problemsSelection") {
    return (
      <TagSelectionScreen
        title="What are your biggest problems right now?"
        subtitle="Select all that apply..."
        background="#480B1D"
        sections={Object.entries(problemsBySection)}
        selected={selectedProblems}
        setSelected={setSelectedProblems}
        max={99}
        onContinue={() => setCurrentStep("goalsSelection")}
      />
    );
  }

  if (currentStep === "goalsSelection") {
    return (
      <TagSelectionScreen
        title="What do you want to achieve with peptides?"
        subtitle="Select up to three goals..."
        background="#152417"
        sections={[["Goals", goalsOptions]]}
        selected={selectedGoals}
        setSelected={setSelectedGoals}
        max={3}
        onContinue={() => setCurrentStep("photoCapture")}
      />
    );
  }

  if (currentStep === "photoCapture") {
    return (
      <PhotoCaptureScreen
        capturedImageUrl={capturedImageUrl}
        setCapturedImageUrl={setCapturedImageUrl}
        onContinue={() => setCurrentStep("scanning")}
      />
    );
  }

  if (currentStep === "scanning") {
    return (
      <ScanningScreen
        onComplete={() => {
          const finalPeptides = peptidesByIds(selectedPeptideIds);
          setMatchedPeptides(finalPeptides);
          setCurrentStep("results");
        }}
      />
    );
  }

  return (
    <ResultsScreen
      userName={userName || "Creator"}
      userImageUrl={capturedImageUrl}
      peptides={matchedPeptides}
      userRole={userRole}
      editorRating={userRole === "Editor" || (isBPCreator && selectedContentGoal === "Transformation") ? editorRating : null}
      onTap={resetFlow}
      onContinueToApp={() => enterMainApp(matchedPeptides, selectedContentGoal, userRole === "Editor" ? editorRating : null)}
    />
  );
}

function CardScreen(props: { title: string; subtitle: string; children: React.ReactNode }) {
  return (
    <div className="screen white center">
      <div className="glass-card">
        <h2 className="brand">{props.title}</h2>
        <p className="card-subtitle">{props.subtitle}</p>
        {props.children}
      </div>
    </div>
  );
}

function PeptideSelectionScreen(props: {
  selectedIds: Set<string>;
  setSelectedIds: (ids: Set<string>) => void;
  maxSelections: number;
  onContinue: () => void;
}) {
  const [selectedCategory, setSelectedCategory] = useState("All");
  const categories = useMemo(() => allPeptideCategories(), []);
  const filtered = useMemo(() => {
    if (selectedCategory === "All") {
      return peptides;
    }
    return peptides.filter((peptide) => peptide.category === selectedCategory);
  }, [selectedCategory]);

  return (
    <div className="screen white">
      <div className="header-block">
        <h3>What peptides do you want in your video?</h3>
        <p>Select {props.maxSelections} peptides to proceed</p>
        <div className="dot-indicator">
          {Array.from({ length: props.maxSelections }).map((_, index) => (
            <span key={index} className={cn("dot", index < props.selectedIds.size && "active")} />
          ))}
        </div>
      </div>

      <div className="chips-scroll">
        {categories.map((category) => (
          <button
            key={category}
            type="button"
            className={cn("chip", selectedCategory === category && "active")}
            onClick={() => setSelectedCategory(category)}
          >
            {category}
          </button>
        ))}
      </div>

      <div className="peptide-grid">
        {filtered.map((peptide) => {
          const isSelected = props.selectedIds.has(peptide.id);
          const isDisabled = !isSelected && props.selectedIds.size >= props.maxSelections;

          return (
            <button
              key={peptide.id}
              type="button"
              className={cn("peptide-chip", isSelected && "selected", isDisabled && "disabled")}
              onClick={() => {
                const next = new Set(props.selectedIds);
                if (isSelected) {
                  next.delete(peptide.id);
                } else if (next.size < props.maxSelections) {
                  next.add(peptide.id);
                }
                props.setSelectedIds(next);
              }}
              disabled={isDisabled}
            >
              <div>
                <h4>{peptide.commonName}</h4>
                <p>{peptide.category}</p>
              </div>
              {isSelected ? <span className="checkmark">✓</span> : null}
            </button>
          );
        })}
      </div>

      {props.selectedIds.size === props.maxSelections ? (
        <div className="floating-cta">
          <button type="button" className="primary-pill" onClick={props.onContinue}>
            CONTINUE →
          </button>
        </div>
      ) : null}
    </div>
  );
}

function RatingScreen(props: { rating: EditorRatingData; onChange: (rating: EditorRatingData) => void; onContinue: () => void }) {
  const [showCurrent, setShowCurrent] = useState(false);
  const [showPotential, setShowPotential] = useState(false);
  const tiers = tiersForGender(props.rating.gender);

  return (
    <div className="screen white">
      <div className="header-block compact">
        <h3>Customize your rating card</h3>
        <p>Set the scores for your character</p>
      </div>

      <div className="rating-content">
        <div className="rating-block">
          <label>GENDER</label>
          <div className="segmented">
            {["Male", "Female"].map((gender) => (
              <button
                key={gender}
                type="button"
                className={cn("seg-btn", props.rating.gender === gender && "active")}
                onClick={() => {
                  const nextGender = gender as "Male" | "Female";
                  const nextTiers = tiersForGender(nextGender);
                  props.onChange({
                    ...props.rating,
                    gender: nextGender,
                    currentRating: nextTiers.includes(props.rating.currentRating) ? props.rating.currentRating : nextTiers[5],
                    potentialRating: nextTiers.includes(props.rating.potentialRating) ? props.rating.potentialRating : nextTiers[9],
                  });
                }}
              >
                {gender}
              </button>
            ))}
          </div>
        </div>

        <div className="rating-block">
          <label>PSL SCORE</label>
          <div className="slider-header">
            <strong>{props.rating.pslScore}</strong>
          </div>
          <input
            className="score-slider"
            type="range"
            min={1}
            max={8}
            value={props.rating.pslScore}
            onChange={(event) => props.onChange({ ...props.rating, pslScore: Number(event.target.value) })}
          />
        </div>

        <RatingPicker
          label="CURRENT RATING"
          isOpen={showCurrent}
          setIsOpen={setShowCurrent}
          selected={props.rating.currentRating}
          options={tiers}
          onSelect={(next) => props.onChange({ ...props.rating, currentRating: next })}
        />

        <RatingPicker
          label="POTENTIAL RATING"
          isOpen={showPotential}
          setIsOpen={setShowPotential}
          selected={props.rating.potentialRating}
          options={tiers}
          onSelect={(next) => props.onChange({ ...props.rating, potentialRating: next })}
        />
      </div>

      <div className="floating-cta">
        <button type="button" className="primary-pill" onClick={props.onContinue}>
          CONTINUE →
        </button>
      </div>
    </div>
  );
}

function RatingPicker(props: {
  label: string;
  isOpen: boolean;
  setIsOpen: (value: boolean) => void;
  selected: string;
  options: string[];
  onSelect: (next: string) => void;
}) {
  return (
    <div className="rating-block">
      <label>{props.label}</label>
      <button type="button" className="picker-button" onClick={() => props.setIsOpen(!props.isOpen)}>
        <span>{props.selected}</span>
        <span>{props.isOpen ? "▴" : "▾"}</span>
      </button>
      {props.isOpen ? (
        <div className="tiers-grid">
          {props.options.map((option) => (
            <button
              key={option}
              type="button"
              className={cn("tier-pill", props.selected === option && "active")}
              onClick={() => {
                props.onSelect(option);
                props.setIsOpen(false);
              }}
            >
              {option}
            </button>
          ))}
        </div>
      ) : null}
    </div>
  );
}

function TagSelectionScreen(props: {
  title: string;
  subtitle: string;
  background: string;
  sections: Array<[string, readonly (readonly [string, string])[] | Array<[string, string]>]>;
  selected: Set<string>;
  setSelected: (set: Set<string>) => void;
  max: number;
  onContinue: () => void;
}) {
  return (
    <div className="screen" style={{ background: props.background }}>
      <div className="dark-header">
        <h3>{props.title}</h3>
        <p>{props.subtitle}</p>
      </div>
      <div className="dark-scroll">
        {props.sections.map(([sectionName, options]) => (
          <section key={sectionName} className="dark-section">
            <h4>{sectionName}</h4>
            <div className="stack-12">
              {options.map(([label, icon]) => {
                const selected = props.selected.has(label);
                return (
                  <button
                    key={label}
                    type="button"
                    className={cn("option-row", selected && "active")}
                    onClick={() => {
                      const next = new Set(props.selected);
                      if (next.has(label)) {
                        next.delete(label);
                      } else if (next.size < props.max) {
                        next.add(label);
                      }
                      props.setSelected(next);
                    }}
                  >
                    <span>{icon}</span>
                    <span>{label}</span>
                    <span>{selected ? "✓" : "○"}</span>
                  </button>
                );
              })}
            </div>
          </section>
        ))}
      </div>

      {props.selected.size > 0 ? (
        <div className="floating-cta">
          <button type="button" className="light-pill" onClick={props.onContinue}>
            continue →
          </button>
        </div>
      ) : null}
    </div>
  );
}

function PhotoCaptureScreen(props: {
  capturedImageUrl: string | null;
  setCapturedImageUrl: (url: string | null) => void;
  onContinue: () => void;
}) {
  const [previewUrl, setPreviewUrl] = useState<string | null>(props.capturedImageUrl);
  const [isVideo, setIsVideo] = useState(false);
  const [progress, setProgress] = useState(0);
  const [statusText, setStatusText] = useState("Analyzing...");

  useEffect(() => {
    if (!previewUrl) {
      return;
    }

    const reset = window.setTimeout(() => {
      setProgress(0);
      setStatusText("Analyzing...");
    }, 0);
    const timeout1 = window.setTimeout(() => setStatusText("Hold still..."), 500);
    const timeout2 = window.setTimeout(() => setStatusText("Finalizing..."), 1000);

    const interval = window.setInterval(() => {
      setProgress((value) => {
        if (value >= 1) {
          window.clearInterval(interval);
          return 1;
        }
        return value + 0.025;
      });
    }, 40);

    const done = window.setTimeout(() => {
      props.setCapturedImageUrl(previewUrl);
      props.onContinue();
    }, 1800);

    return () => {
      window.clearTimeout(reset);
      window.clearTimeout(timeout1);
      window.clearTimeout(timeout2);
      window.clearTimeout(done);
      window.clearInterval(interval);
    };
  }, [previewUrl, props]);

  return (
    <div className="screen black center">
      {previewUrl ? (
        <div className="photo-preview-stage">
          {isVideo ? <video src={previewUrl} autoPlay muted loop className="preview-media" /> : <img src={previewUrl} alt="Captured" className="preview-media" />}
          <div className="face-oval">
            <span style={{ transform: `scaleX(${progress})` }} />
          </div>
          <p>{statusText}</p>
        </div>
      ) : (
        <div className="glass-card dark">
          <h2 className="brand white">REGEN</h2>
          <p className="card-subtitle">Take a Selfie for Analysis</p>
          <p className="body-copy">Use good lighting and face the camera directly.</p>
          <label className="primary-pill upload">
            OPEN CAMERA / LIBRARY →
            <input
              type="file"
              accept="image/*,video/*"
              capture="user"
              onChange={(event) => {
                const file = event.target.files?.[0];
                if (!file) {
                  return;
                }
                const nextUrl = URL.createObjectURL(file);
                setIsVideo(file.type.startsWith("video"));
                setPreviewUrl(nextUrl);
              }}
            />
          </label>
        </div>
      )}
    </div>
  );
}

function ScanningScreen(props: { onComplete: () => void }) {
  const [percentage, setPercentage] = useState(0);

  useEffect(() => {
    const start = Date.now();
    const duration = 5000;
    const timer = window.setInterval(() => {
      const elapsed = Date.now() - start;
      const next = Math.min(100, Math.round((elapsed / duration) * 100));
      setPercentage(next);
      if (next >= 100) {
        window.clearInterval(timer);
        window.setTimeout(props.onComplete, 450);
      }
    }, 50);
    return () => window.clearInterval(timer);
  }, [props]);

  return (
    <div className="screen white center">
      <div className="scan-head">
        <h2 className="brand">REGEN</h2>
      </div>
      <div className="progress-ring">
        <div className="ring-value">{percentage}%</div>
      </div>
      <div className="scan-bullets">
        {loadingBullets.map((bullet, idx) => (
          <div key={bullet} className={cn("scan-bullet", percentage >= (idx + 1) * 25 && "done")}>
            <span>{percentage >= (idx + 1) * 25 ? "✓" : "○"}</span>
            <span>{bullet}</span>
          </div>
        ))}
      </div>
      <p className="scan-status">generating your results...</p>
    </div>
  );
}

function ResultsScreen(props: {
  userName: string;
  userImageUrl: string | null;
  peptides: Peptide[];
  userRole: UserRole;
  editorRating: EditorRatingData | null;
  onTap: () => void;
  onContinueToApp: () => void;
}) {
  const peptideCount = props.userRole === "Editor" ? 2 : 3;
  return (
    <div className="screen white center" onClick={props.onTap}>
      <div className="results-card">
        <div className="results-header">
          <span className="logo-badge">R</span>
          <span className="app-badge">⌂</span>
        </div>
        <div className="results-avatar">
          {props.userImageUrl ? <img src={props.userImageUrl} alt="User" /> : <span>👤</span>}
        </div>
        <p className="results-label">REGEN APP</p>
        <h3>{props.editorRating ? props.editorRating.currentRating : props.userName.toUpperCase()}</h3>

        {props.editorRating ? (
          <div className="rating-bars">
            <div>
              <label>PSL Score</label>
              <strong>{props.editorRating.pslScore}</strong>
              <div className="meter">
                <span style={{ width: `${(props.editorRating.pslScore / 8) * 100}%` }} />
              </div>
            </div>
            <div>
              <label>Potential</label>
              <strong>{props.editorRating.potentialRating}</strong>
              <div className="meter">
                <span style={{ width: `${tierProgress(props.editorRating.potentialRating, props.editorRating.gender) * 100}%` }} />
              </div>
            </div>
          </div>
        ) : null}

        <div className="result-peptide-list">
          <p>{props.userRole === "Editor" ? "YOUR PEPTIDE CYCLE:" : "YOUR CYCLE:"}</p>
          {props.peptides.slice(0, peptideCount).map((peptide) => (
            <PeptideCard key={peptide.id} peptide={peptide} />
          ))}
        </div>
      </div>
      <p className="tap-hint">Tap to continue</p>
    </div>
  );
}

function MainAppView(props: {
  appState: CreatorAppState;
  mainTab: number;
  setMainTab: (tab: number) => void;
  onRestart: () => void;
}) {
  const tabs = ["Home", "Explore", "Regen AI", "Journey", "Profile"];

  return (
    <div className="main-app">
      <div className="main-content">
        {props.mainTab === 0 ? <HomeTab appState={props.appState} /> : null}
        {props.mainTab === 1 ? <ExploreTab /> : null}
        {props.mainTab === 2 ? <ChatTab /> : null}
        {props.mainTab === 3 ? <JourneyTab /> : null}
        {props.mainTab === 4 ? <ProfileTab appState={props.appState} onRestart={props.onRestart} /> : null}
      </div>
      <div className="tab-bar">
        {tabs.map((label, index) => (
          <button key={label} type="button" className={cn("tab-btn", props.mainTab === index && "active")} onClick={() => props.setMainTab(index)}>
            {label}
          </button>
        ))}
      </div>
    </div>
  );
}

function HomeTab(props: { appState: CreatorAppState }) {
  const goal = props.appState.contentGoal?.toUpperCase() ?? "OVERVIEW";

  return (
    <div className="tab-scroll">
      <div className="home-header">
        <div>
          <p>{goal}</p>
          <h2>{props.appState.contentGoal === "Transformation" ? "Transform Now" : "Dashboard"}</h2>
        </div>
        <div className="mini-avatar">{props.appState.userImageUrl ? <img src={props.appState.userImageUrl} alt="profile" /> : "👤"}</div>
      </div>
      <div className="focus-card">
        <h3>{props.appState.contentGoal === "Transformation" ? "Transformation Journey" : "Optimized Cycle Plan"}</h3>
        <p>{props.appState.userName}&apos;s Alpha Stack</p>
      </div>
      <section>
        <p className="section-label">ACTIVE PROTOCOL</p>
        <div className="stack-12">
          {props.appState.selectedPeptides.map((peptide) => (
            <PeptideCard key={peptide.id} peptide={peptide} />
          ))}
        </div>
      </section>
    </div>
  );
}

function ExploreTab() {
  const [filter, setFilter] = useState("All");
  const [search, setSearch] = useState("");
  const filters = ["All", "Weight Loss", "Muscle & Height", "Skin Health", "Focus and Memory", "Recovery"];

  const filtered = peptides.filter((peptide) => {
    const matchesSearch = peptide.commonName.toLowerCase().includes(search.toLowerCase());
    const matchesFilter =
      filter === "All" ||
      (filter === "Weight Loss" && peptide.category === "Fat Loss") ||
      (filter === "Muscle & Height" && peptide.category === "Muscle") ||
      (filter === "Skin Health" && ["Skin", "Aesthetics"].includes(peptide.category)) ||
      (filter === "Focus and Memory" && ["Cognitive", "Nootropic"].includes(peptide.category)) ||
      (filter === "Recovery" && peptide.category === "Recovery");
    return matchesSearch && matchesFilter;
  });

  return (
    <div className="tab-scroll">
      <input className="search-input" placeholder="Search compounds..." value={search} onChange={(event) => setSearch(event.target.value)} />
      <div className="chips-scroll">
        {filters.map((item) => (
          <button key={item} type="button" className={cn("chip", filter === item && "active")} onClick={() => setFilter(item)}>
            {item}
          </button>
        ))}
      </div>
      <div className="product-grid">
        {filtered.map((peptide) => (
          <div key={peptide.id} className="product-card">
            <div className="product-image">🧪</div>
            <h4>{peptide.commonName}</h4>
            <span>{peptide.category}</span>
          </div>
        ))}
      </div>
    </div>
  );
}

function ChatTab() {
  const [messages, setMessages] = useState([
    { text: "Hello! I am Regen AI. Your protocol has been initialized based on your scan.", isUser: false },
    { text: "How can I help you optimize your routine today?", isUser: false },
  ]);
  const [input, setInput] = useState("");

  return (
    <div className="chat-wrap">
      <header>Regen AI</header>
      <div className="chat-list">
        {messages.map((message, idx) => (
          <div key={`${message.text}-${idx}`} className={cn("bubble-row", message.isUser && "user")}>
            <div className={cn("bubble", message.isUser && "user")}>{message.text}</div>
          </div>
        ))}
      </div>
      <div className="chat-input-row">
        <input value={input} onChange={(event) => setInput(event.target.value)} placeholder="Ask anything..." />
        <button
          type="button"
          onClick={() => {
            if (!input.trim()) return;
            const text = input;
            setInput("");
            setMessages((prev) => [...prev, { text, isUser: true }, { text: `Based on your scan, here's a practical protocol note about ${text}.`, isUser: false }]);
          }}
        >
          ↑
        </button>
      </div>
    </div>
  );
}

function JourneyTab() {
  return (
    <div className="tab-scroll">
      <h2 className="journey-title">Your Journey</h2>
      <div className="journey-list">
        {Array.from({ length: 5 }).map((_, index) => (
          <div key={index} className="journey-item">
            <span className={cn("timeline-dot", index === 0 && "active")} />
            <div>
              <h4>{index === 0 ? "Today" : `Week ${index}`}</h4>
              <p>Protocol Check-in</p>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

function ProfileTab(props: { appState: CreatorAppState; onRestart: () => void }) {
  return (
    <div className="tab-scroll profile">
      <div className="profile-head">
        <div className="profile-avatar">{props.appState.userImageUrl ? <img src={props.appState.userImageUrl} alt="profile" /> : "👤"}</div>
        <h3>{props.appState.userName}</h3>
        <span>Standard Plan</span>
      </div>
      <div className="settings-list">
        {["Account Settings", "Notifications", "Privacy & Security", "Support"].map((item) => (
          <button key={item} type="button" className="setting-row">
            <span>{item}</span>
            <span>›</span>
          </button>
        ))}
      </div>
      <button type="button" className="restart-button" onClick={props.onRestart}>
        Restart Creator Flow
      </button>
    </div>
  );
}

function PeptideCard(props: { peptide: Peptide }) {
  return (
    <div className="peptide-card">
      <div className="image-wrap">
        {props.peptide.imageUrl ? <img src={props.peptide.imageUrl} alt={props.peptide.commonName} /> : <span>🧪</span>}
      </div>
      <div className="peptide-copy">
        <h4>{props.peptide.commonName.toUpperCase()}</h4>
        <p>{props.peptide.subtitle}</p>
        <small>
          {props.peptide.usageGuide?.frequency ?? "Weekly"} • {props.peptide.protocol?.displayMetric ?? "N/A"} | 20.0 U
        </small>
      </div>
      <span className="category-tag">{props.peptide.category}</span>
    </div>
  );
}

export const creatorGradient = primaryGradient;
