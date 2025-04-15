# ReelBlendr: AI-Powered Video Reel Creator

ReelBlendr is a web application that allows users to upload video clips and automatically generate stylized video reels using AI. It combines a Next.js frontend with a Python backend for video processing and analysis.

## Key Features

*   **Video Upload:** Upload video files directly or select them from Google Drive. (Google Photos integration planned).
*   **Customization:** Define target duration, content focus, key themes, visual style, mood, genre, and clip order.
*   **Audio Integration:** Choose to add background music by selecting a Spotify track (with recommendations) or opt for no audio.
*   **AI Video Generation:** The backend processes uploaded videos, analyzes content, and creates a final video reel based on user preferences.
*   **Video Playback:** View the generated video directly within the application.
*   **Dynamic UI:** Features a modern interface with dynamic backgrounds and loading indicators.

## Technologies Used

**Frontend:**
*   [Next.js](https://nextjs.org/) (React Framework)
*   [React](https://reactjs.org/)
*   [TypeScript](https://www.typescriptlang.org/)
*   [Tailwind CSS](https://tailwindcss.com/)
*   [Shadcn/ui](https://ui.shadcn.com/) (UI Components)
*   [Lucide React](https://lucide.dev/) (Icons)
*   [Video.js](https://videojs.com/) (Video Player)
*   [React Dropzone](https://react-dropzone.js.org/) (File Uploads)
*   [Google API Client Library for JavaScript](https://github.com/google/google-api-javascript-client) (Google Drive Integration)
*   [Google Identity Services](https://developers.google.com/identity/gsi/web) (Google Authentication)

**Backend:**
*   [Python](https://www.python.org/)
*   [Flask/FastAPI/Other](https://flask.palletsprojects.com/) (Web framework assumed based on `app.py` and API structure)
*   [Google Cloud Video Intelligence API](https://cloud.google.com/video-intelligence)
*   [Google Cloud Generative AI API](https://cloud.google.com/vertex-ai/docs/generative-ai/start/quickstarts/quickstart-multimodal) (Potentially)
*   [MoviePy](https://zulko.github.io/moviepy/) (Video Editing)
*   [FFmpeg](https://ffmpeg.org/) (via `ffmpeg-python`) (Video Processing)
*   [Gradio](https://www.gradio.app/) (Potentially for testing/demos)

## Setup and Installation

### Prerequisites

*   Node.js (v20 or later recommended)
*   npm or yarn or pnpm
*   Python (3.8 or later recommended)
*   pip (Python package installer)
*   FFmpeg installed and available in your system's PATH.
*   Google Cloud Project with:
    *   Video Intelligence API enabled.
    *   Generative AI API enabled (if used).
    *   OAuth 2.0 Client ID credentials (for Web application).
    *   API Key (restricted appropriately).

### Environment Variables

You will need to set up environment variables for Google Cloud credentials. Create a `.env` file in the root directory and potentially in the `backend` directory.

**Frontend (root `.env.local`):**
```
NEXT_PUBLIC_GOOGLE_API_KEY=YOUR_GOOGLE_API_KEY
NEXT_PUBLIC_GOOGLE_CLIENT_ID=YOUR_GOOGLE_OAUTH_CLIENT_ID.apps.googleusercontent.com
# Add any other frontend-specific variables (e.g., Spotify API keys if used client-side)
```
*(Note: The current code hardcodes these in `app/components/VideoCreationForm.tsx`. It is strongly recommended to move them to environment variables as shown above for security and flexibility.)*

**Backend (`backend/.env`):**
```
GOOGLE_APPLICATION_CREDENTIALS=path/to/your/google-service-account-key.json
# Add any other backend-specific variables (e.g., Spotify API keys if used server-side)
```

### Installation

1.  **Clone the repository:**
    ```bash
    git clone <repository-url>
    cd reel
    ```

2.  **Install frontend dependencies:**
    ```bash
    npm install
    # or
    # yarn install
    # or
    # pnpm install
    ```

3.  **Install backend dependencies:**
    ```bash
    cd backend
    python -m venv venv
    # Activate the virtual environment
    # Windows:
    # venv\Scripts\activate
    # macOS/Linux:
    # source venv/bin/activate
    pip install -r requirements.txt
    cd ..
    ```

## Running the Application

1.  **Start the backend server:**
    *   Navigate to the `backend` directory.
    *   Ensure your virtual environment is activated.
    *   Set the `GOOGLE_APPLICATION_CREDENTIALS` environment variable if not using a `.env` file loader in the backend.
    *   Run the Python application (the exact command might depend on the framework used, e.g., `flask run` or `python app.py`).
    ```bash
    cd backend
    # source venv/bin/activate  or  venv\Scripts\activate
    # export GOOGLE_APPLICATION_CREDENTIALS="path/to/your/key.json" # Example for Linux/macOS
    # set GOOGLE_APPLICATION_CREDENTIALS="path/to/your/key.json" # Example for Windows CMD
    # $env:GOOGLE_APPLICATION_CREDENTIALS="path/to/your/key.json" # Example for Windows PowerShell
    python app.py # Or the appropriate command for your backend framework
    cd ..
    ```

2.  **Start the frontend development server:**
    *   In the root directory:
    ```bash
    npm run dev
    # or
    # yarn dev
    # or
    # pnpm dev
    ```

3.  **Open the application:**
    Open [http://localhost:3000](http://localhost:3000) in your browser.

## Project Structure

```
reel/
├── app/                  # Next.js App Router directory
│   ├── api/              # API routes (frontend proxies/handlers)
│   ├── components/       # React components
│   │   └── inputs/       # Input-specific components
│   ├── ui/               # Shadcn/ui components
│   ├── globals.css       # Global styles
│   ├── layout.tsx        # Root layout
│   └── page.tsx          # Main page component
├── backend/              # Python backend
│   ├── data/             # Data files (e.g., analysis results)
│   │   └── output/       # Output video storage (likely)
│   ├── venv/             # Python virtual environment (if created)
│   ├── app.py            # Main backend application file (assumed)
│   ├── music_recommender.py # Music recommendation logic
│   ├── requirements.txt  # Backend Python dependencies
│   ├── video_analyzer.py # Video analysis logic
│   ├── video_creator.py  # Video creation logic
│   ├── video_editor.py   # Video editing logic
│   └── video_processor.py # Video processing logic
├── lib/                  # Utility functions
├── public/               # Static assets
├── .env.local            # Frontend environment variables (create this)
├── .gitignore
├── components.json       # Shadcn/ui config
├── next.config.ts        # Next.js configuration
├── package.json          # Frontend dependencies and scripts
├── README.md             # This file
└── tsconfig.json         # TypeScript configuration
```

## Contributing

Contributions are welcome! Please follow standard Git workflow (fork, branch, pull request).

## License

[Specify License Here - e.g., MIT]
