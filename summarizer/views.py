from django.contrib.auth.models import User
from django.contrib.auth import authenticate, login, logout
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.views.decorators.csrf import csrf_exempt
from django.http import JsonResponse
import json
from urllib.parse import unquote
import yt_dlp
import assemblyai as aai
import os
from django.conf import settings
from .models import VideoSummary
from django.http import StreamingHttpResponse
import time

@login_required
def index(request):
    return render(request, 'index.html')

@csrf_exempt
def generate_summary(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            yt_link = unquote(data['link'])
            print(f"Processing YouTube link: {yt_link}")
            
            # Update progress message
            request.session['progress_message'] = "Processing YouTube link..."
            
        except (KeyError, json.JSONDecodeError) as e:
            print(f"Data parsing error: {str(e)}")
            return JsonResponse({'error': 'Invalid data sent'}, status=400)

        try:
            # Get YouTube video title
            request.session['progress_message'] = "Fetching video title..."
            title = yt_title(yt_link)
            
            # Get the transcription and summary
            request.session['progress_message'] = "Downloading audio file..."
            audio_file = download_audio(yt_link)
            
            request.session['progress_message'] = "Converting audio to text..."
            result = get_transcription(yt_link)
            
            transcription = result['transcription']
            summary_content = result['summary']
            
            request.session['progress_message'] = "Processing completed, generating summary..."
            
        except Exception as e:
            import traceback
            print(f"Processing error: {str(e)}")
            print(traceback.format_exc())
            return JsonResponse({'error': f"Error: {str(e)}"}, status=400)

        if not transcription or not summary_content:
            return JsonResponse({'error': "Failed to process video"}, status=500)

        try:
            request.session['progress_message'] = "Saving summary to database..."
            new_summary = VideoSummary.objects.create(
                user=request.user,
                youtube_title=title,
                youtube_link=yt_link,
                summary_content=summary_content,
            )
            new_summary.save()
            
            request.session['progress_message'] = "Summary generated successfully!"
            return JsonResponse({'content': summary_content})
            
        except Exception as e:
            import traceback
            print(f"Database error: {str(e)}")
            print(traceback.format_exc())
            return JsonResponse({'error': f"Error: {str(e)}"}, status=500)

    return JsonResponse({'error': 'Invalid request method'}, status=405)

def yt_title(link):
    """Fetch the YouTube video title."""
    ydl_opts = {
        'format': 'best',
    }
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(link, download=False)
        return info.get('title')

def download_audio(link):
    """Download audio from YouTube video link."""
    try:
        # Use MEDIA_ROOT directly instead of creating an audio subfolder
        media_path = settings.MEDIA_ROOT
        os.makedirs(media_path, exist_ok=True)

        ydl_opts = {
            'format': 'bestaudio/best',
            'postprocessors': [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'mp3',
                'preferredquality': '192',
            }],
            'outtmpl': os.path.join(media_path, '%(id)s.%(ext)s'),
            'verbose': True
        }

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            print("Starting download...")
            info = ydl.extract_info(link, download=True)
            file_path = os.path.join(media_path, f"{info['id']}.mp3")
            print(f"Download completed. File path: {file_path}")
            
            if not os.path.exists(file_path):
                raise Exception(f"Audio file not found at {file_path}")
                
            return file_path
    except Exception as e:
        print(f"Error in download_audio: {str(e)}")
        raise

def get_transcription(link):
    """Get transcription from audio file using AssemblyAI."""
    try:
        print("Starting download_audio...")
        audio_file = download_audio(link)
        print(f"Audio file downloaded successfully: {audio_file}")
        
        print("Setting up AssemblyAI...")
        aai.settings.api_key = "394cdb03355a4f3e89b331815f9337e6"
        
        print("Creating transcriber...")
        transcriber = aai.Transcriber()
        config = aai.TranscriptionConfig(
            summarization=True,
            summary_model=aai.SummarizationModel.informative,
            summary_type=aai.SummarizationType.paragraph
        )
        
        print("Starting transcription...")
        transcript = transcriber.transcribe(audio_file, config=config)
        print("Transcription completed successfully")
        
        if not transcript.text or not transcript.summary:
            raise Exception("Transcription or summary is empty")
        
        return {
            'transcription': transcript.text,
            'summary': transcript.summary
        }
    except Exception as e:
        import traceback
        print(f"Transcription error: {str(e)}")
        print("Full traceback:")
        print(traceback.format_exc())
        raise

def user_login(request):
    """Handle user login."""
    if request.method == 'POST':
        username = request.POST['username']
        password = request.POST['password']
        
        user = authenticate(request, username=username, password=password)
        if user is not None:
            login(request, user)
            return redirect('/')
        else:
            error_message = "Invalid username or password"
            return render(request, 'login.html', {'error_message': error_message})
    
    return render(request, 'login.html')


def user_signup(request):
    """Handle user signup."""
    if request.method == 'POST':
        username = request.POST['username']
        email = request.POST['email']
        password = request.POST['password']
        repeatPassword = request.POST['repeatPassword']
        
        if password == repeatPassword:
            try:
                user = User.objects.create_user(username, email, password)
                user.save()
                login(request, user)
                return redirect('/')
            except:
                error_message = 'Error creating account'
                return render(request, 'signup.html', {'error_message': error_message})
        else:
            error_message = 'Passwords do not match'
            return render(request, 'signup.html', {'error_message': error_message})
        
    return render(request, 'signup.html')

def user_logout(request):
    """Handle user logout."""
    logout(request)
    return redirect('/')

def progress(request):
    def event_stream():
        last_message = None
        while True:
            current_message = request.session.get('progress_message')
            if current_message and current_message != last_message:
                last_message = current_message
                yield f"data: {json.dumps({'message': current_message})}\n\n"
            time.sleep(0.5)

    response = StreamingHttpResponse(event_stream(), content_type='text/event-stream')
    response['Cache-Control'] = 'no-cache'
    response['Connection'] = 'keep-alive'
    return response


def all_summaries(request):
    video_summaries = VideoSummary.objects.filter(user=request.user).order_by('-created_at')
    return render(request, 'all-summaries.html', {
        'video_summaries': video_summaries,
        'user': request.user
    })

@login_required
def video_summaries(request):
    # Get all summaries for the current user
    summaries = VideoSummary.objects.filter(user=request.user).order_by('-created_at')
    # Add print statement for debugging
    print(f"Found {len(summaries)} summaries for user {request.user.username}")
    return render(request, 'all-summaries.html', {'video_summaries': summaries})

@login_required
def summary_details(request, pk):
    summary = get_object_or_404(VideoSummary, pk=pk, user=request.user)
    return render(request, 'video-summary-details.html', {'video_summary': summary})


def contact(request):
    return render(request, 'contact.html')