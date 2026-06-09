/**
 * 语音RAG集成模块
 * ==================
 *
 * 为QAPanel.vue提供高性能语音RAG功能
 * 不修改原有代码，作为独立模块使用
 *
 * 使用方法：
 * 1. 在QAPanel.vue中引入此模块
 * 2. 调用 initVoiceRAG() 初始化
 * 3. 使用 startVoiceRecording() 和 stopVoiceRecording() 控制录音
 *
 * @version 1.0.0
 * @author AI Assistant
 */

class VoiceRAGIntegration {
    constructor(options = {}) {
        // 配置选项
        this.config = {
            serviceUrl: options.serviceUrl || 'http://localhost:8087',
            maxRecordingTime: options.maxRecordingTime || 30000, // 30秒
            sampleRate: options.sampleRate || 16000,
            channels: options.channels || 1,
            enableCache: options.enableCache !== false,
            autoPlay: options.autoPlay !== false,
            ...options
        };

        // 状态管理
        this.isRecording = false;
        this.isProcessing = false;
        this.mediaRecorder = null;
        this.audioStream = null;
        this.audioChunks = [];
        this.audioContext = null;

        // 回调函数
        this.callbacks = {
            onRecordingStart: null,
            onRecordingStop: null,
            onTranscriptionReceived: null,
            onResponseReceived: null,
            onError: null,
            onStatusChange: null
        };

        // 缓存
        this.responseCache = new Map();

        console.log('🎤 VoiceRAG集成模块已初始化');
    }

    /**
     * 设置回调函数
     */
    setCallbacks(callbacks) {
        Object.assign(this.callbacks, callbacks);
    }

    /**
     * 初始化音频上下文
     */
    async initAudioContext() {
        try {
            this.audioContext = new (window.AudioContext || window.webkitAudioContext)();
            console.log('✅ 音频上下文初始化成功');
            return true;
        } catch (error) {
            console.error('❌ 音频上下文初始化失败:', error);
            return false;
        }
    }

    /**
     * 检查服务状态
     */
    async checkServiceStatus() {
        try {
            const response = await fetch(`${this.config.serviceUrl}/api/health`);
            const data = await response.json();

            if (response.ok && data.status === 'healthy') {
                console.log('✅ 语音RAG服务连接正常');
                return true;
            } else {
                console.warn('⚠️ 语音RAG服务状态异常:', data);
                return false;
            }
        } catch (error) {
            console.error('❌ 无法连接到语音RAG服务:', error);
            return false;
        }
    }

    /**
     * 开始录音
     */
    async startVoiceRecording() {
        if (this.isRecording) {
            console.warn('⚠️ 录音已在进行中');
            return false;
        }

        try {
            // 请求麦克风权限
            this.audioStream = await navigator.mediaDevices.getUserMedia({
                audio: {
                    sampleRate: this.config.sampleRate,
                    channelCount: this.config.channels,
                    echoCancellation: true,
                    noiseSuppression: true,
                    autoGainControl: true
                }
            });

            // 初始化音频上下文
            if (!this.audioContext) {
                await this.initAudioContext();
            }

            // 创建MediaRecorder
            this.mediaRecorder = new MediaRecorder(this.audioStream, {
                mimeType: 'audio/webm;codecs=opus'
            });

            this.audioChunks = [];

            // 监听数据可用事件
            this.mediaRecorder.ondataavailable = (event) => {
                if (event.data.size > 0) {
                    this.audioChunks.push(event.data);
                }
            };

            // 监听停止事件
            this.mediaRecorder.onstop = async () => {
                await this.processRecordedAudio();
            };

            // 开始录音
            this.mediaRecorder.start(100); // 每100ms收集一次数据
            this.isRecording = true;

            // 设置最大录音时间
            setTimeout(() => {
                if (this.isRecording) {
                    this.stopVoiceRecording();
                }
            }, this.config.maxRecordingTime);

            // 触发回调
            if (this.callbacks.onRecordingStart) {
                this.callbacks.onRecordingStart();
            }

            if (this.callbacks.onStatusChange) {
                this.callbacks.onStatusChange('recording');
            }

            console.log('🎙️ 开始录音');
            return true;

        } catch (error) {
            console.error('❌ 启动录音失败:', error);
            this.isRecording = false;

            if (this.callbacks.onError) {
                this.callbacks.onError('无法访问麦克风，请检查权限设置');
            }

            return false;
        }
    }

    /**
     * 停止录音
     */
    stopVoiceRecording() {
        if (!this.isRecording) {
            console.warn('⚠️ 当前没有在录音');
            return false;
        }

        try {
            // 停止录音
            if (this.mediaRecorder && this.mediaRecorder.state === 'recording') {
                this.mediaRecorder.stop();
            }

            // 停止音频流
            if (this.audioStream) {
                this.audioStream.getTracks().forEach(track => track.stop());
            }

            this.isRecording = false;

            // 触发回调
            if (this.callbacks.onRecordingStop) {
                this.callbacks.onRecordingStop();
            }

            if (this.callbacks.onStatusChange) {
                this.callbacks.onStatusChange('processing');
            }

            console.log('⏹️ 停止录音');
            return true;

        } catch (error) {
            console.error('❌ 停止录音失败:', error);
            return false;
        }
    }

    /**
     * 处理录制的音频
     */
    async processRecordedAudio() {
        if (this.isProcessing) {
            console.warn('⚠️ 音频处理已在进行中');
            return;
        }

        this.isProcessing = true;

        try {
            // 合并音频块
            const audioBlob = new Blob(this.audioChunks, { type: 'audio/webm' });

            if (audioBlob.size === 0) {
                throw new Error('录音数据为空');
            }

            console.log(`📁 音频数据大小: ${(audioBlob.size / 1024).toFixed(2)} KB`);

            // 转换为WAV格式（如果需要）
            const wavBlob = await this.convertToWav(audioBlob);

            // 转换为Base64
            const base64Audio = await this.blobToBase64(wavBlob);

            // 发送到语音RAG服务
            const result = await this.sendToVoiceRAGService(base64Audio);

            // 处理结果
            await this.handleServiceResponse(result);

        } catch (error) {
            console.error('❌ 音频处理失败:', error);

            if (this.callbacks.onError) {
                this.callbacks.onError(`音频处理失败: ${error.message}`);
            }
        } finally {
            this.isProcessing = false;

            if (this.callbacks.onStatusChange) {
                this.callbacks.onStatusChange('idle');
            }
        }
    }

    /**
     * 转换音频为WAV格式
     */
    async convertToWav(audioBlob) {
        try {
            // 如果已经是WAV格式，直接返回
            if (audioBlob.type.includes('wav')) {
                return audioBlob;
            }

            // 使用Web Audio API转换
            const arrayBuffer = await audioBlob.arrayBuffer();
            const audioBuffer = await this.audioContext.decodeAudioData(arrayBuffer);

            // 转换为WAV
            const wavBuffer = this.audioBufferToWav(audioBuffer);
            return new Blob([wavBuffer], { type: 'audio/wav' });

        } catch (error) {
            console.warn('⚠️ 音频格式转换失败，使用原始格式:', error);
            return audioBlob;
        }
    }

    /**
     * AudioBuffer转WAV
     */
    audioBufferToWav(buffer) {
        const length = buffer.length;
        const arrayBuffer = new ArrayBuffer(44 + length * 2);
        const view = new DataView(arrayBuffer);
        const sampleRate = buffer.sampleRate;

        // WAV文件头
        const writeString = (offset, string) => {
            for (let i = 0; i < string.length; i++) {
                view.setUint8(offset + i, string.charCodeAt(i));
            }
        };

        writeString(0, 'RIFF');
        view.setUint32(4, 36 + length * 2, true);
        writeString(8, 'WAVE');
        writeString(12, 'fmt ');
        view.setUint32(16, 16, true);
        view.setUint16(20, 1, true);
        view.setUint16(22, 1, true);
        view.setUint32(24, sampleRate, true);
        view.setUint32(28, sampleRate * 2, true);
        view.setUint16(32, 2, true);
        view.setUint16(34, 16, true);
        writeString(36, 'data');
        view.setUint32(40, length * 2, true);

        // 音频数据
        const channelData = buffer.getChannelData(0);
        let offset = 44;
        for (let i = 0; i < length; i++) {
            const sample = Math.max(-1, Math.min(1, channelData[i]));
            view.setInt16(offset, sample * 0x7FFF, true);
            offset += 2;
        }

        return arrayBuffer;
    }

    /**
     * Blob转Base64
     */
    blobToBase64(blob) {
        return new Promise((resolve, reject) => {
            const reader = new FileReader();
            reader.onloadend = () => resolve(reader.result);
            reader.onerror = reject;
            reader.readAsDataURL(blob);
        });
    }

    /**
     * 发送到语音RAG服务
     */
    async sendToVoiceRAGService(base64Audio) {
        const startTime = Date.now();

        try {
            const response = await fetch(`${this.config.serviceUrl}/api/voice/process`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    audio_data: base64Audio,
                    format: 'wav'
                })
            });

            if (!response.ok) {
                throw new Error(`服务器返回错误: ${response.status}`);
            }

            const result = await response.json();
            const processingTime = Date.now() - startTime;

            console.log(`⚡ 语音处理完成，耗时: ${processingTime}ms`);

            return result;

        } catch (error) {
            console.error('❌ 语音RAG服务请求失败:', error);
            throw error;
        }
    }

    /**
     * 处理服务响应
     */
    async handleServiceResponse(result) {
        try {
            if (!result.success) {
                throw new Error(result.error || '处理失败');
            }

            console.log('📝 转录结果:', result.transcription);
            console.log('🤖 AI回复:', result.response_text);

            // 触发转录回调
            if (this.callbacks.onTranscriptionReceived) {
                this.callbacks.onTranscriptionReceived(result.transcription);
            }

            // 触发响应回调
            if (this.callbacks.onResponseReceived) {
                this.callbacks.onResponseReceived({
                    transcription: result.transcription,
                    response: result.response_text,
                    audioUrl: result.audio_url,
                    processingTime: result.processing_time
                });
            }

            // 自动播放语音（如果启用）
            if (this.config.autoPlay && result.audio_url) {
                await this.playAudioResponse(result.audio_url);
            }

            // 缓存响应（如果启用）
            if (this.config.enableCache) {
                this.cacheResponse(result.transcription, result.response_text);
            }

        } catch (error) {
            console.error('❌ 处理服务响应失败:', error);

            if (this.callbacks.onError) {
                this.callbacks.onError(error.message);
            }
        }
    }

    /**
     * 播放音频响应
     */
    async playAudioResponse(audioUrl) {
        try {
            if (!audioUrl) {
                console.warn('⚠️ 没有音频URL');
                return;
            }

            // 创建音频元素
            const audio = new Audio(audioUrl);

            // 播放音频
            await audio.play();

            console.log('🔊 开始播放AI语音回复');

        } catch (error) {
            console.error('❌ 播放音频失败:', error);
        }
    }

    /**
     * 缓存响应
     */
    cacheResponse(transcription, response) {
        if (this.responseCache.size >= 100) {
            // 清理最旧的缓存
            const firstKey = this.responseCache.keys().next().value;
            this.responseCache.delete(firstKey);
        }

        this.responseCache.set(transcription.toLowerCase().trim(), {
            response,
            timestamp: Date.now()
        });
    }

    /**
     * 获取缓存响应
     */
    getCachedResponse(transcription) {
        const key = transcription.toLowerCase().trim();
        const cached = this.responseCache.get(key);

        if (cached && Date.now() - cached.timestamp < 300000) { // 5分钟有效
            return cached.response;
        }

        return null;
    }

    /**
     * 清理资源
     */
    cleanup() {
        try {
            if (this.isRecording) {
                this.stopVoiceRecording();
            }

            if (this.audioContext) {
                this.audioContext.close();
                this.audioContext = null;
            }

            this.responseCache.clear();

            console.log('🧹 VoiceRAG资源清理完成');

        } catch (error) {
            console.error('❌ 资源清理失败:', error);
        }
    }

    /**
     * 获取状态信息
     */
    getStatus() {
        return {
            isRecording: this.isRecording,
            isProcessing: this.isProcessing,
            cacheSize: this.responseCache.size,
            serviceUrl: this.config.serviceUrl
        };
    }
}

/**
 * 工厂函数，创建VoiceRAG实例
 */
function createVoiceRAG(options = {}) {
    return new VoiceRAGIntegration(options);
}

/**
 * Vue 3 组合式API插件
 */
function useVoiceRAG(options = {}) {
    const { ref, onMounted, onUnmounted } = Vue;

    const voiceRAG = ref(null);
    const isRecording = ref(false);
    const isProcessing = ref(false);
    const transcription = ref('');
    const response = ref('');
    const error = ref('');

    onMounted(() => {
        voiceRAG.value = createVoiceRAG(options);

        // 设置回调
        voiceRAG.value.setCallbacks({
            onRecordingStart: () => {
                isRecording.value = true;
                error.value = '';
            },
            onRecordingStop: () => {
                isRecording.value = false;
                isProcessing.value = true;
            },
            onTranscriptionReceived: (text) => {
                transcription.value = text;
            },
            onResponseReceived: (result) => {
                response.value = result.response;
                isProcessing.value = false;
            },
            onError: (err) => {
                error.value = err;
                isRecording.value = false;
                isProcessing.value = false;
            },
            onStatusChange: (status) => {
                if (status === 'idle') {
                    isProcessing.value = false;
                }
            }
        });
    });

    onUnmounted(() => {
        if (voiceRAG.value) {
            voiceRAG.value.cleanup();
        }
    });

    const startRecording = () => voiceRAG.value?.startVoiceRecording();
    const stopRecording = () => voiceRAG.value?.stopVoiceRecording();
    const checkService = () => voiceRAG.value?.checkServiceStatus();

    return {
        voiceRAG,
        isRecording,
        isProcessing,
        transcription,
        response,
        error,
        startRecording,
        stopRecording,
        checkService
    };
}

// 导出模块
if (typeof module !== 'undefined' && module.exports) {
    // Node.js环境
    module.exports = {
        VoiceRAGIntegration,
        createVoiceRAG,
        useVoiceRAG
    };
} else {
    // 浏览器环境
    window.VoiceRAGIntegration = VoiceRAGIntegration;
    window.createVoiceRAG = createVoiceRAG;
    window.useVoiceRAG = useVoiceRAG;
}