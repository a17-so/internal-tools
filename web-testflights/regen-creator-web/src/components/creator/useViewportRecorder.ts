"use client";

import { RefObject, useMemo, useRef, useState } from "react";

type RecorderStatus = "idle" | "recording" | "stopping";

type RecorderState = {
  status: RecorderStatus;
  error: string | null;
  supportsRegionCrop: boolean;
  startRecording: () => Promise<void>;
  stopRecording: () => void;
};

type CropTrack = MediaStreamTrack & {
  cropTo?: (target: unknown) => Promise<void>;
};

type CropTargetApi = {
  fromElement?: (element: Element) => Promise<unknown>;
};

export function useViewportRecorder(targetRef: RefObject<HTMLElement | null>): RecorderState {
  const [status, setStatus] = useState<RecorderStatus>("idle");
  const [error, setError] = useState<string | null>(null);
  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const streamRef = useRef<MediaStream | null>(null);
  const chunksRef = useRef<BlobPart[]>([]);

  const supportsRegionCrop = useMemo(() => {
    if (typeof window === "undefined") {
      return false;
    }
    return typeof (window as unknown as { CropTarget?: CropTargetApi }).CropTarget?.fromElement === "function";
  }, []);

  const cleanup = () => {
    streamRef.current?.getTracks().forEach((track) => track.stop());
    streamRef.current = null;
    mediaRecorderRef.current = null;
    chunksRef.current = [];
  };

  const startRecording = async () => {
    setError(null);

    if (!navigator.mediaDevices?.getDisplayMedia) {
      setError("Screen recording is not supported by this browser.");
      return;
    }

    try {
      const stream = await navigator.mediaDevices.getDisplayMedia({
        video: {
          frameRate: 60,
        },
        audio: true,
      });

      streamRef.current = stream;

      const [videoTrack] = stream.getVideoTracks();
      if (videoTrack && targetRef.current && supportsRegionCrop) {
        const cropApi = (window as unknown as { CropTarget?: CropTargetApi }).CropTarget;
        const cropTarget = await cropApi?.fromElement?.(targetRef.current);
        if (cropTarget && typeof (videoTrack as CropTrack).cropTo === "function") {
          await (videoTrack as CropTrack).cropTo?.(cropTarget);
        }
      }

      const mimeType = MediaRecorder.isTypeSupported("video/webm;codecs=vp9")
        ? "video/webm;codecs=vp9"
        : "video/webm";

      const recorder = new MediaRecorder(stream, { mimeType });
      mediaRecorderRef.current = recorder;
      chunksRef.current = [];

      recorder.ondataavailable = (event) => {
        if (event.data.size > 0) {
          chunksRef.current.push(event.data);
        }
      };

      recorder.onstop = () => {
        const blob = new Blob(chunksRef.current, { type: mimeType });
        const url = URL.createObjectURL(blob);
        const a = document.createElement("a");
        const now = new Date();
        const stamp = `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, "0")}-${String(now.getDate()).padStart(2, "0")}_${String(now.getHours()).padStart(2, "0")}-${String(now.getMinutes()).padStart(2, "0")}-${String(now.getSeconds()).padStart(2, "0")}`;
        a.href = url;
        a.download = `regen-creator-recording-${stamp}.webm`;
        a.click();
        URL.revokeObjectURL(url);
        cleanup();
        setStatus("idle");
      };

      recorder.onerror = () => {
        cleanup();
        setStatus("idle");
        setError("Recording failed. Please try again.");
      };

      recorder.start(250);
      setStatus("recording");
    } catch {
      cleanup();
      setStatus("idle");
      setError("Recording canceled or permission denied.");
    }
  };

  const stopRecording = () => {
    if (status !== "recording") {
      return;
    }

    setStatus("stopping");
    mediaRecorderRef.current?.stop();
  };

  return {
    status,
    error,
    supportsRegionCrop,
    startRecording,
    stopRecording,
  };
}
