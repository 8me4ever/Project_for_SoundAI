import os
import base64
import requests
import subprocess
import tempfile
from typing import Dict, Any
from datetime import datetime, timedelta


class BaiduTranscriber:
    """百度语音转写器"""

    TOKEN_URL = "https://aip.baidubce.com/oauth/2.0/token"
    ASR_URL = "https://vop.baidu.com/server_api"

    def __init__(self, api_key: str, secret_key: str):
        self.api_key = api_key
        self.secret_key = secret_key
        self.access_token = None
        self.token_expire_time = None

        if not all([api_key, secret_key]):
            raise ValueError("请提供完整的百度API认证信息")

        self._check_ffmpeg()
        self._get_access_token()

    #检查本地是否安装ffmpeg
    def _check_ffmpeg(self):
        try:
            subprocess.run(["ffmpeg", "-version"], stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)
        except Exception as e:
            raise RuntimeError("未检测到 ffmpeg，请先安装并添加到系统 PATH，或将ffmpeg.exe放置在文件夹下") from e

    #转码音频
    def _convert_audio_to_pcm(self, audio_path: str) -> str:
        temp_dir = tempfile.mkdtemp(prefix="baidu_audio_")
        output_path = os.path.join(temp_dir, "converted_audio.pcm")

        #格式标准
        cmd = [
            "ffmpeg", "-y",
            "-i", audio_path,
            "-ac", "1",
            "-ar", "16000",
            "-acodec", "pcm_s16le",
            "-f", "s16le",
            output_path
        ]

        result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        if result.returncode != 0:
            raise RuntimeError("ffmpeg 转码失败，请检查输入音频或 ffmpeg 安装：\n" + (result.stderr or ""))

        return output_path

    #获取百度API的 access token
    def _get_access_token(self):
        params = {
            'grant_type': 'client_credentials',
            'client_id': self.api_key,
            'client_secret': self.secret_key
        }
        response = requests.post(self.TOKEN_URL, params=params, timeout=15)
        result = response.json()

        if 'access_token' in result:
            self.access_token = result['access_token']
            self.token_expire_time = datetime.now() + timedelta(days=29)
        else:
            raise RuntimeError(result.get('error_description', '获取 Access Token 失败'))

    def _check_token(self):
        if not self.access_token or not self.token_expire_time or datetime.now() >= self.token_expire_time:
            self._get_access_token()

    #读取音频文件并转为base64
    def _get_file_content(self, audio_path: str) -> str:
        with open(audio_path, 'rb') as f:
            audio_data = f.read()
        return base64.b64encode(audio_data).decode('utf-8')

    def transcribe(self, audio_path: str, language: str = 'zh') -> Dict[str, Any]:
        try:
            if not os.path.exists(audio_path):
                return {'success': False, 'error': '音频文件不存在'}

            #标准化转码音频格式
            converted_path = self._convert_audio_to_pcm(audio_path)

            #验证转码后文件是否符合10MB限制
            file_size = os.path.getsize(converted_path)
            if file_size > 10 * 1024 * 1024:
                return {'success': False, 'error': '文件大小超过10MB限制'}

            #检查token
            self._check_token()

            #读文件为base64
            audio_base64 = self._get_file_content(converted_path)

            #百度转写在中文中支持如下语言
            dev_pid_map = {
                'zh': 1537,      # 普通话
                'zh_en': 1737,   # 中英文混合
                'en': 1737,      # 英语
                'ct': 1637,      # 粤语
                'sc': 1837       # 四川话
            }

            params = {
                'format': 'pcm',
                'rate': 16000,
                'channel': 1,
                'cuid': 'python_demo',
                'token': self.access_token,
                'dev_pid': dev_pid_map.get(language, 1537),
                'speech': audio_base64,
                'len': file_size
            }
            headers = {'Content-Type': 'application/json'}

            #调用接口
            response = requests.post(self.ASR_URL, json=params, headers=headers, timeout=30)
            result = response.json()

            #解析结果
            if result.get('err_no') == 0:
                text_list = result.get('result', [])
                text = ''.join(text_list) if text_list else ''
                if not text:
                    return {'success': False, 'error': '未识别到语音内容'}
                return {'success': True, 'text': text}
            else:
                msg = result.get('err_msg', '识别失败')
                return {'success': False, 'error': f'识别失败: {msg}'}

        except requests.exceptions.Timeout:
            return {'success': False, 'error': '请求超时，请重试'}
        except Exception as e:
            return {'success': False, 'error': f'转写失败: {e}'}

    def transcribe_with_details(self, audio_path: str) -> Dict[str, Any]:
        return self.transcribe(audio_path)