import { useState, useRef, useCallback } from 'react';
import { Mic, MicOff, Loader2, Upload, Pause, Play } from 'lucide-react';
import { uploadNote } from '../../services/api';
import { showToast } from '../common/Toast';
import { useUIStore } from '../../store';

// Web Speech API for real-time recognition (free, browser-built-in)
const SpeechRecognition = (window as any).SpeechRecognition || (window as any).webkitSpeechRecognition;

export default function VoiceRecorder() {
  const [recording, setRecording] = useState(false);
  const [paused, setPaused] = useState(false);
  const [transcript, setTranscript] = useState('');
  const [sending, setSending] = useState(false);
  const [hasSupport, setHasSupport] = useState(true);
  const recognitionRef = useRef<any>(null);
  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const chunksRef = useRef<Blob[]>([]);
  const closeUpload = useUIStore((s) => s.closeUpload);

  // Check browser support
  useState(() => {
    if (!SpeechRecognition) {
      setHasSupport(false);
    }
  });

  const startRecording = useCallback(async () => {
    setTranscript('');
    chunksRef.current = [];

    try {
      // Start audio recording (for backup/file save)
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      const mediaRecorder = new MediaRecorder(stream, { mimeType: 'audio/webm' });
      mediaRecorderRef.current = mediaRecorder;

      mediaRecorder.ondataavailable = (e) => {
        if (e.data.size > 0) chunksRef.current.push(e.data);
      };

      mediaRecorder.start(1000); // collect data every second

      // Start speech recognition
      if (SpeechRecognition) {
        const recognition = new SpeechRecognition();
        recognition.lang = 'zh-CN';
        recognition.interimResults = true;
        recognition.continuous = true;
        recognition.maxAlternatives = 1;

        recognition.onresult = (event: any) => {
          let final = '';
          let interim = '';
          for (let i = event.resultIndex; i < event.results.length; i++) {
            const r = event.results[i];
            if (r.isFinal) {
              final += r[0].transcript;
            } else {
              interim += r[0].transcript;
            }
          }
          setTranscript((prev) => {
            // Replace interim, keep finals
            const parts = prev.split('...');
            const allFinal = (parts[0] ? parts[0] + ' ' : '') + final;
            return allFinal + (interim ? '...' + interim : '');
          });
        };

        recognition.onerror = (event: any) => {
          if (event.error === 'no-speech') return;
          if (event.error === 'aborted') return;
          console.warn('Speech recognition error:', event.error);
        };

        recognition.onend = () => {
          // Auto-restart if still recording
          if (recording && !paused) {
            try { recognition.start(); } catch {}
          }
        };

        recognitionRef.current = recognition;
        recognition.start();
      }

      setRecording(true);
      setPaused(false);
    } catch (err: any) {
      if (err.name === 'NotAllowedError') {
        showToast('error', '麦克风权限被拒绝', '请在浏览器设置中允许麦克风访问');
      } else {
        showToast('error', '无法启动录音', err.message);
      }
    }
  }, [recording, paused]);

  const stopRecording = useCallback(() => {
    // Stop speech recognition
    if (recognitionRef.current) {
      recognitionRef.current.stop();
      recognitionRef.current = null;
    }

    // Stop media recorder
    if (mediaRecorderRef.current && mediaRecorderRef.current.state !== 'inactive') {
      mediaRecorderRef.current.stop();
      mediaRecorderRef.current.stream.getTracks().forEach((t: any) => t.stop());
      mediaRecorderRef.current = null;
    }

    setRecording(false);
    setPaused(false);

    // Clean up interim markers
    setTranscript((prev) => prev.replace(/\.\.\.[^.]*$/, '').trim());
  }, []);

  const togglePause = () => {
    if (paused) {
      // Resume
      if (recognitionRef.current) {
        try { recognitionRef.current.start(); } catch {}
      }
      if (mediaRecorderRef.current && mediaRecorderRef.current.state === 'paused') {
        mediaRecorderRef.current.resume();
      }
      setPaused(false);
    } else {
      // Pause
      if (recognitionRef.current) {
        recognitionRef.current.stop();
      }
      if (mediaRecorderRef.current && mediaRecorderRef.current.state === 'recording') {
        mediaRecorderRef.current.pause();
      }
      setPaused(true);
    }
  };

  const sendToKnowledgeBase = async () => {
    const text = transcript.trim();
    if (!text) {
      showToast('warning', '没有识别到文字', '请先录音');
      return;
    }

    setSending(true);
    try {
      const result = await uploadNote(text, '语音笔记');
      if (result.status === 'ok') {
        showToast('success', '语音笔记已保存', `分类: ${result.category}`);
        setTranscript('');
        closeUpload();
      } else if (result.status === 'duplicate') {
        showToast('warning', '内容已存在');
      }
    } catch (err: any) {
      showToast('error', '保存失败', err.message);
    }
    setSending(false);
  };

  if (!hasSupport) {
    return (
      <div className="p-6 text-center">
        <MicOff size={32} className="mx-auto mb-3 text-gray-600" />
        <p className="text-gray-400 text-sm">当前浏览器不支持语音识别</p>
        <p className="text-gray-600 text-xs mt-1">请使用 Chrome 或 Edge 浏览器</p>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      {/* Record button */}
      <div className="flex items-center justify-center gap-4 py-4">
        {!recording ? (
          <button
            onClick={startRecording}
            className="w-16 h-16 rounded-full bg-gradient-to-br from-red-500 to-pink-500
                       flex items-center justify-center shadow-lg shadow-red-500/30
                       hover:scale-110 transition-all active:scale-95"
          >
            <Mic size={28} className="text-white" />
          </button>
        ) : (
          <div className="flex items-center gap-4">
            <button
              onClick={togglePause}
              className="w-12 h-12 rounded-full bg-amber-500/20 border border-amber-500/30
                         flex items-center justify-center hover:scale-110 transition-all"
            >
              {paused ? <Play size={20} className="text-amber-400" /> : <Pause size={20} className="text-amber-400" />}
            </button>
            <div className="w-16 h-16 rounded-full bg-red-500 flex items-center justify-center animate-pulse">
              <Mic size={28} className="text-white" />
            </div>
            <button
              onClick={stopRecording}
              className="w-12 h-12 rounded-full bg-gray-700 border border-gray-600
                         flex items-center justify-center hover:scale-110 transition-all"
            >
              <MicOff size={20} className="text-gray-400" />
            </button>
          </div>
        )}
      </div>

      <p className="text-center text-xs text-gray-500">
        {recording
          ? paused ? '⏸ 已暂停' : '🔴 正在录音...'
          : '点击开始录音，语音自动转文字'}
      </p>

      {/* Transcript display */}
      <div className="relative">
        <textarea
          value={transcript}
          onChange={(e) => setTranscript(e.target.value)}
          placeholder="录音内容将在这里显示..."
          rows={6}
          className="input-field resize-none text-sm"
          readOnly={recording}
        />
        {recording && (
          <div className="absolute top-2 right-2">
            <span className="w-2 h-2 rounded-full bg-red-500 animate-pulse inline-block" />
          </div>
        )}
      </div>

      {/* Actions */}
      {transcript.trim() && !recording && (
        <button
          onClick={sendToKnowledgeBase}
          disabled={sending}
          className="btn-primary w-full flex items-center justify-center gap-2 py-2.5"
        >
          {sending ? <Loader2 size={16} className="animate-spin" /> : <Upload size={16} />}
          {sending ? '保存中...' : `保存到知识库 (${transcript.length} 字)`}
        </button>
      )}
    </div>
  );
}
