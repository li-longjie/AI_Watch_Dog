/**
 * QAPanel语音RAG集成补丁
 * ========================
 *
 * 这个文件将为现有的QAPanel.vue添加语音RAG功能
 * 不修改原有代码，通过扩展的方式集成新功能
 *
 * 使用方法：
 * 1. 在QAPanel.vue的<script setup>部分末尾添加：
 *    import './voice_rag_integration_patch.js';
 * 2. 重新启动前端应用
 * 3. 点击语音按钮时会自动使用新的语音RAG服务
 */

// 等待Vue组件加载完成
document.addEventListener('DOMContentLoaded', function() {
    console.log('🎤 语音RAG集成补丁已加载');

    // 语音RAG服务配置
    const VOICE_RAG_CONFIG = {
        serviceUrl: 'http://localhost:8087',
        fallbackToOriginal: true,  // 如果新服务不可用，回退到原始服务
        enableDebugLog: true
    };

    // 调试日志函数
    function debugLog(...args) {
        if (VOICE_RAG_CONFIG.enableDebugLog) {
            console.log('[VoiceRAG]', ...args);
        }
    }

    // 检查语音RAG服务是否可用
    async function checkVoiceRAGService() {
        try {
            const response = await fetch(`${VOICE_RAG_CONFIG.serviceUrl}/api/health`, {
                method: 'GET',
                timeout: 2000
            });

            if (response.ok) {
                const data = await response.json();
                debugLog('✅ 语音RAG服务可用:', data);
                return true;
            } else {
                debugLog('⚠️ 语音RAG服务状态异常:', response.status);
                return false;
            }
        } catch (error) {
            debugLog('❌ 语音RAG服务不可用:', error.message);
            return false;
        }
    }

    // 将音频Blob转换为Base64
    function blobToBase64(blob) {
        return new Promise((resolve, reject) => {
            const reader = new FileReader();
            reader.onloadend = () => resolve(reader.result);
            reader.onerror = reject;
            reader.readAsDataURL(blob);
        });
    }

    // 发送音频到语音RAG服务
    async function sendToVoiceRAGService(audioBlob) {
        try {
            debugLog('📤 发送音频到语音RAG服务...');

            // 转换为Base64
            const base64Audio = await blobToBase64(audioBlob);

            // 发送请求
            const response = await fetch(`${VOICE_RAG_CONFIG.serviceUrl}/api/voice/process`, {
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
            debugLog('📥 收到语音RAG响应:', result);

            return result;

        } catch (error) {
            debugLog('❌ 语音RAG服务请求失败:', error);
            throw error;
        }
    }

    // 播放音频文件
    function playAudioFile(audioPath) {
        if (!audioPath) return;

        try {
            const audio = new Audio(audioPath);
            audio.play().then(() => {
                debugLog('🔊 开始播放AI语音回复');
            }).catch(error => {
                debugLog('❌ 播放音频失败:', error);
            });
        } catch (error) {
            debugLog('❌ 创建音频对象失败:', error);
        }
    }

    // 扩展现有的语音功能
    function enhanceVoiceFeatures() {
        // 查找Vue应用实例
        const app = document.querySelector('#app').__vueParentComponent;
        if (!app) {
            debugLog('❌ 未找到Vue应用实例');
            return;
        }

        debugLog('✅ 找到Vue应用实例，开始增强语音功能');

        // 存储原始的音频处理函数
        let originalSendAudioToWhisperAPI = null;

        // 查找并替换语音处理逻辑
        const vueInstance = app.ctx;
        if (vueInstance && vueInstance.sendAudioToWhisperAPI) {
            originalSendAudioToWhisperAPI = vueInstance.sendAudioToWhisperAPI;

            // 替换为增强版本
            vueInstance.sendAudioToWhisperAPI = async function(audioBlob) {
                debugLog('🎯 拦截语音处理请求');

                // 检查语音RAG服务是否可用
                const isVoiceRAGAvailable = await checkVoiceRAGService();

                if (isVoiceRAGAvailable) {
                    try {
                        // 使用语音RAG服务
                        const result = await sendToVoiceRAGService(audioBlob);

                        if (result.success) {
                            // 更新识别文本
                            if (vueInstance.recognizedText) {
                                vueInstance.recognizedText.value = result.transcription;
                            }

                            // 自动发送消息（如果有回复）
                            if (result.response_text && vueInstance.userInput && vueInstance.messages) {
                                // 添加用户消息
                                vueInstance.messages.value.push({
                                    id: Date.now(),
                                    sender: 'user',
                                    text: result.transcription
                                });

                                // 添加AI回复
                                vueInstance.messages.value.push({
                                    id: Date.now() + 1,
                                    sender: 'ai',
                                    text: result.response_text
                                });

                                // 播放语音回复
                                if (result.audio_url) {
                                    playAudioFile(result.audio_url);
                                }

                                debugLog('✅ 语音RAG处理完成');
                                return;
                            }
                        } else {
                            debugLog('⚠️ 语音RAG处理失败:', result.error);
                        }
                    } catch (error) {
                        debugLog('❌ 语音RAG处理异常:', error);
                    }
                }

                // 回退到原始服务
                if (VOICE_RAG_CONFIG.fallbackToOriginal && originalSendAudioToWhisperAPI) {
                    debugLog('🔄 回退到原始Whisper服务');
                    return await originalSendAudioToWhisperAPI.call(this, audioBlob);
                } else {
                    debugLog('❌ 无可用的语音服务');
                }
            };

            debugLog('✅ 语音处理函数已增强');
        } else {
            debugLog('❌ 未找到语音处理函数');
        }
    }

    // 监听Vue应用加载
    function waitForVueApp() {
        const checkInterval = setInterval(() => {
            const app = document.querySelector('#app');
            if (app && app.__vueParentComponent) {
                clearInterval(checkInterval);
                setTimeout(enhanceVoiceFeatures, 1000); // 延迟1秒确保组件完全加载
            }
        }, 500);

        // 10秒后停止检查
        setTimeout(() => {
            clearInterval(checkInterval);
            debugLog('⏰ Vue应用检查超时');
        }, 10000);
    }

    // 开始监听
    waitForVueApp();
});

// 如果在模块环境中，也提供直接调用的方法
if (typeof window !== 'undefined') {
    window.VoiceRAGPatch = {
        // 手动触发语音RAG增强
        enhance: function() {
            debugLog('🔧 手动触发语音RAG增强');
            enhanceVoiceFeatures();
        },

        // 测试语音RAG服务
        testService: async function() {
            try {
                const response = await fetch('http://localhost:8087/api/health');
                const data = await response.json();
                console.log('✅ 语音RAG服务测试结果:', data);
                return true;
            } catch (error) {
                console.log('❌ 语音RAG服务测试失败:', error);
                return false;
            }
        }
    };
}