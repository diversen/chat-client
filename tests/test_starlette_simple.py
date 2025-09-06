"""
Simple test for basic Starlette backend functionality
"""
import os
import sys
from unittest.mock import patch

# Add project root to path
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

from starlette.testclient import TestClient


def test_basic_routes():
    """Test basic routes with minimal setup"""
    print("Testing basic routes...")
    
    # Import app directly without complex mocking
    from chat_client.main import app
    
    with TestClient(app) as client:
        # Test error endpoint - should work without auth
        response = client.post("/error/log", json={"error": "test"})
        assert response.status_code == 200, f"Error endpoint failed: {response.text}"
        print("✓ Error endpoint works")
        
        # Test redirect to login for protected route
        with patch('chat_client.core.user_session.is_logged_in', return_value=False):
            response = client.get("/")
            assert response.status_code in [200, 307], f"Protected route unexpected status: {response.status_code}"
            if response.status_code == 307:
                assert "/user/login" in response.headers.get("location", "")
            print("✓ Protected route handling works")
        
        # Test config endpoint
        response = client.get("/config")
        assert response.status_code == 200, f"Config endpoint failed: {response.text}"
        data = response.json()
        assert "default_model" in data
        print("✓ Config endpoint works")
        
        # Test models list endpoint
        response = client.get("/list")
        assert response.status_code == 200, f"List models endpoint failed: {response.text}"
        data = response.json()
        assert "model_names" in data
        assert isinstance(data["model_names"], list)
        print("✓ Models list endpoint works")


def test_user_routes():
    """Test user-related routes"""
    print("Testing user routes...")
    
    from chat_client.main import app
    
    with TestClient(app) as client:
        # Test signup GET
        response = client.get("/user/signup")
        assert response.status_code == 200, f"Signup GET failed: {response.status_code}"
        assert "Sign up" in response.text
        print("✓ Signup GET works")
        
        # Test login GET
        response = client.get("/user/login")
        assert response.status_code == 200, f"Login GET failed: {response.status_code}"
        assert "Login" in response.text
        print("✓ Login GET works")
        
        # Test captcha
        response = client.get("/captcha")
        assert response.status_code == 200, f"Captcha failed: {response.status_code}"
        assert response.headers["content-type"] == "image/png"
        print("✓ Captcha works")
        
        # Test is-logged-in when not authenticated
        with patch('chat_client.core.user_session.is_logged_in', return_value=False):
            response = client.get("/user/is-logged-in")
            assert response.status_code == 200, f"Is-logged-in failed: {response.status_code}"
            data = response.json()
            assert data["error"] is True  # Should be error because not logged in
            print("✓ Is-logged-in endpoint works when not authenticated")


def test_authenticated_routes():
    """Test routes that require authentication"""
    print("Testing authenticated routes...")
    
    from chat_client.main import app
    
    with TestClient(app) as client:
        # Test chat page when authenticated
        with patch('chat_client.core.user_session.is_logged_in', return_value=1):  # Mock logged in user
            with patch('chat_client.repositories.prompt_repository.list_prompts', return_value=[]):
                response = client.get("/")
                assert response.status_code == 200, f"Chat page failed: {response.status_code}"
                assert "Chat" in response.text
                print("✓ Chat page works when authenticated")
            
            # Test is-logged-in when authenticated
            response = client.get("/user/is-logged-in")
            assert response.status_code == 200
            data = response.json()
            assert data["error"] is False  # Should not be error when logged in
            print("✓ Is-logged-in works when authenticated")
            
            # Test prompt list
            with patch('chat_client.repositories.prompt_repository.list_prompts', return_value=[]):
                response = client.get("/prompt")
                assert response.status_code == 200
                print("✓ Prompt list works when authenticated")


def test_json_endpoints():
    """Test JSON API endpoints"""
    print("Testing JSON endpoints...")
    
    from chat_client.main import app
    
    with TestClient(app) as client:
        # Test chat endpoint without auth - should return 401
        with patch('chat_client.core.user_session.is_logged_in', return_value=False):
            response = client.post("/chat", json={
                "messages": [{"role": "user", "content": "test"}],
                "model": "test-model"
            })
            assert response.status_code == 401
            print("✓ Chat endpoint requires authentication")
            
            # Test create dialog without auth - should return 401
            response = client.post("/chat/create-dialog", json={"title": "Test"})
            assert response.status_code == 401
            print("✓ Create dialog endpoint requires authentication")


if __name__ == "__main__":
    print("Running simple Starlette backend tests...")
    print("=" * 50)
    
    try:
        test_basic_routes()
        test_user_routes()
        test_authenticated_routes()
        test_json_endpoints()
        
        print("\n" + "=" * 50)
        print("✅ All basic tests passed!")
        
    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


def main():
    """Main entry point for simple tests"""
    try:
        test_basic_routes()
        test_user_routes()
        test_authenticated_routes()
        test_json_endpoints()
        return True
    except Exception as e:
        print(f"Simple tests failed: {e}")
        return False