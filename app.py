from flask import (
    Flask,
    render_template,
    request,
    Response,
    stream_with_context,
    jsonify,
)
from werkzeug.utils import secure_filename
from PIL import Image
import io
from dotenv import load_dotenv
import os

import google.generativeai as genai

# Load environment variables from .env file
load_dotenv()

ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "txt"}

# WARNING: Do not share code with you API key hard coded in it.
# Get your Gemini API key from: https://aistudio.google.com/app/apikey
genai.configure(api_key=os.getenv("GOOGLE_API_KEY"))

model = genai.GenerativeModel('gemini-1.5-flash')

app = Flask(__name__, static_folder='static', template_folder='templates')

chat_session = model.start_chat(history=[])
next_message = ""
next_image = ""


def allowed_file(filename):
    """Returns if a filename is supported via its extension"""
    _, ext = os.path.splitext(filename)
    return ext.lstrip('.').lower() in ALLOWED_EXTENSIONS


@app.route("/upload", methods=["POST"])
def upload_file():
    """파일을 받아 유효성을 검사하고 다음 API 요청을 위해 저장합니다."""
    global next_image
    global next_text_content

    if "file" not in request.files:
        return jsonify(success=False, message="파일이 없습니다")

    file = request.files["file"]

    if file.filename == "":
        return jsonify(success=False, message="선택된 파일이 없습니다")
    
    if file and allowed_file(file.filename):
        filename = secure_filename(file.filename)
        
        # 파일 스트림을 BytesIO 객체로 읽기
        file_stream = io.BytesIO(file.read())
        file_stream.seek(0)
        
        # 파일 확장자 확인
        _, ext = os.path.splitext(filename)
        if ext.lower() == '.txt':
            # 텍스트 파일 처리
            next_text_content = file_stream.read().decode('utf-8')
            message = "텍스트 파일이 성공적으로 업로드되어 대화에 추가되었습니다"
        else:
            # 이미지 파일 처리
            next_image = Image.open(file_stream)
            message = "이미지 파일이 성공적으로 업로드되어 대화에 추가되었습니다"

        return jsonify(
            success=True,
            message=message,
            filename=filename,
        )
    return jsonify(success=False, message="허용되지 않는 파일 형식입니다")


@app.route("/", methods=["GET"])
def index():
    """Renders the main homepage for the app"""
    return render_template("index.html", chat_history=chat_session.history)


@app.route("/chat", methods=["POST"])
def chat():
    """
    Takes in the message the user wants to send
    to the Gemini API, saves it
    """
    global next_message
    next_message = request.json["message"]
    print(chat_session.history)

    return jsonify(success=True)


@app.route("/stream", methods=["GET"])
def stream():
    """
    Streams the response from the serve for
    both multi-modal and plain text requests
    """
    def generate():
        global next_message
        global next_image
        assistant_response_content = ""

        if next_image != "":
            response = chat_session.send_message([next_message, next_image],
                                                 stream=True)
            next_image = ""
        else:
            response = chat_session.send_message(next_message, stream=True)
            next_message = ""

        for chunk in response:
            assistant_response_content += chunk.text
            yield f"data: {chunk.text}\n\n"

    return Response(stream_with_context(generate()),
                    mimetype="text/event-stream")
