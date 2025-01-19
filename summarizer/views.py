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

# Index view to render the main page; requires user to be logged in
@login_required
def index(request):
    return render(request, 'index.html')

# Function to handle the generation of summaries from YouTube video links
@csrf_exempt
def generate_summary(request):
    # Ensure the request is POST
    if request.method == 'POST':
        try:
            # Parse the incoming JSON data
            data = json.loads(request.body)
            yt_link = unquote(data['link'])  # Decode URL-encoded YouTube link
            print(f"Processing YouTube link: {yt_link}")

            # Update progress message in session
            request.session['progress_message'] = "Processing YouTube link..."

            # Validate if the provided link is a valid YouTube URL
            if not ('youtube.com' in yt_link or 'youtu.be' in yt_link):
                return JsonResponse({'error': 'Invalid YouTube URL'}, status=400)

            try:
                # Fetch video title for the provided link
                request.session['progress_message'] = "Fetching video title..."
                title = yt_title(yt_link)

                # Handle case where the video title could not be retrieved
                if not title:
                    return JsonResponse({'error': 'Could not access video. Please check the URL.'}, status=400)

                # Download audio and process transcription
                request.session['progress_message'] = "Downloading audio file..."
                audio_file = download_audio(yt_link)

                request.session['progress_message'] = "Converting audio to text..."
                result = get_transcription(yt_link)

                transcription = result['transcription']
                summary_content = result['summary']

                # Update progress after transcription is completed
                request.session['progress_message'] = "Processing completed, generating summary..."

            except Exception as e:
                # Handle any errors during processing
                import traceback
                print(f"Processing error: {str(e)}")
                print(traceback.format_exc())
                return JsonResponse({'error': f"Error: {str(e)}"}, status=400)

            # Ensure transcription and summary were successfully generated
            if not transcription or not summary_content:
                return JsonResponse({'error': "Failed to process video"}, status=500)

            try:
                # Save the generated summary to the database
                request.session['progress_message'] = "Saving summary to database..."
                new_summary = VideoSummary.objects.create(
                    user=request.user,
                    youtube_title=title,
                    youtube_link=yt_link,
                    summary_content=summary_content,
                )
                new_summary.save()

                # Update session message to indicate success
                request.session['progress_message'] = "Summary generated successfully!"
                return JsonResponse({'content': summary_content})

            except Exception as e:
                # Handle database errors
                import traceback
                print(f"Database error: {str(e)}")
                print(traceback.format_exc())
                return JsonResponse({'error': f"Error: {str(e)}"}, status=500)

        except (KeyError, json.JSONDecodeError) as e:
            # Handle errors in parsing input data
            print(f"Data parsing error: {str(e)}")
            return JsonResponse({'error': 'Invalid data sent'}, status=400)

    # Return error for non-POST methods
    return JsonResponse({'error': 'Invalid request method'}, status=405)

# Utility function to fetch the title of a YouTube video
def yt_title(link):
    """Fetch the YouTube video title."""
    ydl_opts = {
        'quiet': True,
        'no_warnings': True,
        'extract_flat': True,
        'no_color': True,
        'http_headers': {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'en-us,en;q=0.5',
            'Sec-Fetch-Mode': 'navigate',
        }
    }
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        try:
            info = ydl.extract_info(link, download=False)
            return info.get('title')  # Extract and return video title
        except Exception as e:
            print(f"Error in yt_title: {str(e)}")
            raise

# Function to download audio from a YouTube video link
def download_audio(link):
    """Download audio from YouTube video link."""
    try:
        # Define temporary directory for storing audio files
        temp_dir = '/tmp' if not settings.DEBUG else settings.MEDIA_ROOT
        os.makedirs(temp_dir, exist_ok=True)

        ydl_opts = {
            'format': 'bestaudio/best',
            'postprocessors': [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'mp3',
                'preferredquality': '192',
            }],
            'outtmpl': os.path.join(temp_dir, '%(id)s.%(ext)s'),
            'quiet': True,
            'no_warnings': True,
            'no_color': True,
            'http_headers': {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
                'Accept-Language': 'en-us,en;q=0.5',
                'Sec-Fetch-Mode': 'navigate',
            }
        }

        # Download the audio file
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            print("Starting download...")
            info = ydl.extract_info(link, download=True)
            temp_file_path = os.path.join(temp_dir, f"{info['id']}.mp3")

            # Ensure the audio file was created
            if not os.path.exists(temp_file_path):
                raise Exception(f"Audio file not found at {temp_file_path}")

            # Upload audio to Cloudinary
            from cloudinary.uploader import upload
            result = upload(temp_file_path, resource_type="auto", folder="youtube_audio")

            # Remove temporary file after upload
            os.remove(temp_file_path)

            # Return Cloudinary file URL
            return result['url']

    except Exception as e:
        print(f"Error in download_audio: {str(e)}")
        raise

# Function to handle transcription of audio files using AssemblyAI
def get_transcription(link):
    """Get transcription from audio file using AssemblyAI."""
    try:
        print("Starting download_audio...")
        audio_url = download_audio(link)  # Download audio and get URL
        print(f"Audio file uploaded successfully: {audio_url}")

        print("Setting up AssemblyAI...")
        aai.settings.api_key = "394cdb03355a4f3e89b331815f9337e6"  # Replace with your actual API key

        print("Creating transcriber...")
        transcriber = aai.Transcriber()
        config = aai.TranscriptionConfig(
            summarization=True,
            summary_model=aai.SummarizationModel.informative,
            summary_type=aai.SummarizationType.paragraph
        )

        print("Starting transcription...")
        transcript = transcriber.transcribe(audio_url, config=config)  # Perform transcription
        print("Transcription completed successfully")
        print(transcript.text)

        if not transcript.text or not transcript.summary:
            raise Exception("Transcription or summary is empty")

        # Return transcription and summary
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

# Function to handle user login
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

# Function to handle user signup
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

# Function to handle user logout
def user_logout(request):
    """Handle user logout."""
    logout(request)
    return redirect('/')

# Function to stream real-time progress updates to the client
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

# View to display all summaries for the logged-in user
def all_summaries(request):
    video_summaries = VideoSummary.objects.filter(user=request.user).order_by('-created_at')
    return render(request, 'all-summaries.html', {
        'video_summaries': video_summaries,
        'user': request.user
    })

# View to display summaries for the logged-in user (duplicate logic retained for clarity)
@login_required
def video_summaries(request):
    # Get all summaries for the current user
    summaries = VideoSummary.objects.filter(user=request.user).order_by('-created_at')
    # Add print statement for debugging
    print(f"Found {len(summaries)} summaries for user {request.user.username}")
    return render(request, 'all-summaries.html', {'video_summaries': summaries})

# View to display detailed summary for a specific video summary
@login_required
def summary_details(request, pk):
    summary = get_object_or_404(VideoSummary, pk=pk, user=request.user)
    return render(request, 'video-summary-details.html', {'video_summary': summary})

# View to render the contact page
def contact(request):
    return render(request, 'contact.html')
