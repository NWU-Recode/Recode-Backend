# 🚀 Recode-Backend

**Transform NWU lecture slides into interactive coding exercises for semester-based gamified learning.**

Recode is an educational platform that converts traditional lecture materials into engaging, interactive coding challenges. Built with FastAPI and powered by Supabase, this backend service provides the foundation for a gamified learning experience that adapts to each student's progress.

## 🎯 Project Overview

Recode addresses the challenge of making computer science education more interactive and engaging by:

- **Transforming static slides** into dynamic coding exercises
- **Summarising key points** from educational content automatically
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

### Note: Upload-triggered Challenge Generation

The slides upload endpoints now act as a middleware that triggers challenge generation automatically after a successful slide extraction and topic creation. Generation rules:

- Every upload will create a base weekly challenge for the detected week.
- Weeks 2, 6, 10: also generate a "ruby" special challenge and publish it.
- Weeks 4, 8: also generate an "emerald" special challenge and publish it.
- Week 12: generate a "diamond" special challenge and publish it.

Lecturer-facing generation endpoints have been removed; generation is now triggered automatically by upload to simplify the flow.

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

### 1. Automated Content Processing

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

- [ ] Advanced content processing
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

## Database migration: teaching_assignments

The admin flows now create rows in a new `teaching_assignments` table which links `semesters`, `modules`, and `lecturers`.

1. SQL file is provided at `scripts/create_teaching_assignments.sql`.

2. To apply on Supabase (SQL editor):

- Open your Supabase project → Database → SQL Editor → paste the contents and Run.

3. To apply via psql locally (pwsh example):

```powershell
# On Windows PowerShell (assuming psql is available and environment variables set):
$env:PGHOST='your-db-host'
$env:PGPORT='5432'
$env:PGUSER='postgres'
$env:PGPASSWORD='yourpassword'
$env:PGDATABASE='postgres'
psexec(pwsh) # optional
psql -h $env:PGHOST -p $env:PGPORT -U $env:PGUSER -d $env:PGDATABASE -f "scripts/create_teaching_assignments.sql"
```

4. After applying the migration, admin assign/remove endpoints will:

- POST /admin/assign-lecturer (body: { module_code: "CS101", lecturer_id: 123 })
- POST /admin/remove-lecturer (body: { module_code: "CS101" })

These endpoints will insert/delete rows in `teaching_assignments` and update `modules.lecturer_id` for backward compatibility.

5. Quick curl example for creating a semester (Admin).

```bash
curl -X POST "http://localhost:8000/admin/semesters" \
	-H "Content-Type: application/json" \
	-H "Cookie: YOUR_ADMIN_SESSION_COOKIE" \
	-d '{"year":2026, "term_name":"Semester 1", "start_date":"2026-02-01", "end_date":"2026-06-30", "is_current":true}'
```

If you want, I can tailor the psql snippet to your exact DB credentials or produce a one-line PowerShell-ready command.
