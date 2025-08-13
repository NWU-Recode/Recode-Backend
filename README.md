# 🚀 Recode-Backend

**Transform NWU lecture slides into interactive, NLP-driven coding exercises for semester-based gamified learning.**

Recode is a revolutionary educational platform that leverages natural language processing to convert traditional lecture materials into engaging, interactive coding challenges. Built with FastAPI and powered by Supabase, this backend service provides the foundation for a gamified learning experience that adapts to each student's progress.

## 🎯 Project Overview

Recode addresses the challenge of making computer science education more interactive and engaging by:
- **Transforming static slides** into dynamic coding exercises
- **Leveraging NLP** to understand and process educational content
- **Creating gamified experiences** with semester-based progression
- **Providing real-time feedback** and adaptive learning paths

## 🏗️ Architecture

### Tech Stack
- **FastAPI** - Modern, fast web framework for building APIs
- **Supabase** - Open-source Firebase alternative with PostgreSQL
- **spaCy** - Industrial-strength NLP for content processing
- **Pydantic** - Data validation using Python type hints
- **Uvicorn** - Lightning-fast ASGI server

### Project Structure
```
recode-backend/
├── app/
│   ├── api/
│   │   └── endpoints/
│   │       └── users.py          # User management endpoints
│   ├── core/
│   │   └── config.py             # Application configuration
│   ├── db/
│   │   └── client.py             # Supabase database client
├── tests/                        # Test suite
├── main.py                       # FastAPI application entry point
├── requirements.txt              # Python dependencies
└── .env.example                  # Environment variables template
```

## 🚀 Quick Start

### Prerequisites
- Python 3.8+
- Supabase account and project

### Installation

1. **Clone the repository**
```bash
git clone https://github.com/your-org/recode-backend.git
cd recode-backend
```

2. **Create virtual environment**
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. **Install dependencies**
```bash
pip install -r requirements.txt
```

4. **Set up environment variables**
```bash
cp .env.example .env
# Edit .env with your Supabase credentials
```

5. **Run the application**
```bash
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

### Environment Variables
Create a `.env` file with:
```env
SUPABASE_URL=your_supabase_project_url
SUPABASE_KEY=your_supabase_anon_key
```

## 📚 API Documentation

### Base URL
```
http://localhost:8000
```

### Available Endpoints

#### Users
- `GET /users` - List all users
- `GET /users/{id}` - Get user by ID
- `POST /users` - Create new user
- `PUT /users/{id}` - Update user
- `DELETE /users/{id}` - Delete user

### Interactive Documentation
- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc

## 🔧 Development

### Running Tests
```bash
pytest tests/
```

### Code Quality
```bash
# Format code
black app/

# Type checking
mypy app/

# Linting
flake8 app/
```

### Database Schema
The application uses the following key tables:
- **users** - User management and profiles
- **exercises** - Interactive coding challenges
- **submissions** - User exercise submissions
- **progress** - Learning progress tracking

## 🎯 Key Features

### 1. NLP Content Processing
- **Slide Analysis**: Extract key concepts from lecture slides
- **Code Generation**: Create relevant coding exercises
- **Difficulty Scaling**: Adjust challenge complexity based on student level

### 2. Gamification System
- **Progress Tracking**: Visual learning journey
- **Achievement System**: Badges and milestones
- **Leaderboards**: Competitive elements
- **Streak Counters**: Daily engagement incentives

### 3. Adaptive Learning
- **Personalized Paths**: Tailored to individual progress
- **Real-time Feedback**: Immediate exercise validation
- **Performance Analytics**: Detailed learning insights

## 🔄 Contributing

1. Fork the repository
2. Create your feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add some amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

### Development Guidelines
- Follow PEP 8 style guidelines
- Add tests for new features
- Update documentation
- Ensure all tests pass

## 🗺️ Roadmap

### Phase 1: Core Platform
- [x] Basic API structure
- [x] User management system
- [ ] Exercise generation engine
- [ ] Content upload system

### Phase 2: Intelligence
- [ ] Advanced NLP processing
- [ ] Adaptive difficulty algorithms
- [ ] Performance analytics dashboard

### Phase 3: Gamification
- [ ] Achievement system
- [ ] Leaderboards
- [ ] Social features

### Phase 4: Scale
- [ ] Multi-language support
- [ ] Advanced reporting
- [ ] Integration with LMS platforms

## 📊 Performance

The backend is optimized for:
- **High concurrency**: Async FastAPI handling
- **Low latency**: Efficient database queries
- **Scalability**: Horizontal scaling ready
- **Caching**: Redis integration ready

## 🔐 Security

- **JWT Authentication**: Secure user sessions
- **Rate Limiting**: API abuse prevention
- **Input Validation**: Pydantic models
- **CORS Protection**: Cross-origin security

## 📞 Support

- **Documentation**: [Wiki](https://github.com/your-org/recode-backend/wiki)
- **Issues**: [GitHub Issues](https://github.com/your-org/recode-backend/issues)
- **Discussions**: [GitHub Discussions](https://github.com/your-org/recode-backend/discussions)

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🙏 Acknowledgments

- North-West University for the educational partnership
- FastAPI community for the excellent framework
- Supabase team for the amazing backend-as-a-service
- All contributors who made this project possible

---

**Built with ❤️ by the Recode Team**

