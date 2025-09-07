import React, { createContext, useContext, useState, useEffect } from 'react';
import { authAPI } from '../services/api';
import toast from 'react-hot-toast';

const AuthContext = createContext();

export const useAuth = () => {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
};

export const AuthProvider = ({ children }) => {
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(true);
  const [permissions, setPermissions] = useState([]);

  // Check for existing session on mount
  useEffect(() => {
    checkAuthStatus();
  }, []);

  const checkAuthStatus = async () => {
    try {
      const accessToken = localStorage.getItem('access_token');
      if (accessToken) {
        // Verify token with backend
        const response = await authAPI.getUser();
        setUser(response.data);
        await loadPermissions();
      }
    } catch (error) {
      // Token is invalid or expired
      localStorage.removeItem('access_token');
      localStorage.removeItem('refresh_token');
    } finally {
      setLoading(false);
    }
  };

  const loadPermissions = async () => {
    try {
      const response = await authAPI.getUser();
      setPermissions(response.data.permissions || []);
    } catch (error) {
      console.error('Failed to load permissions:', error);
    }
  };

  const login = async (code) => {
    try {
      setLoading(true);
      const response = await authAPI.login(code);

      const { access_token, refresh_token, user: userData } = response.data;

      // Store tokens
      localStorage.setItem('access_token', access_token);
      localStorage.setItem('refresh_token', refresh_token);

      // Set user data
      setUser(userData);
      await loadPermissions();

      toast.success('Successfully logged in!');
      return { success: true };

    } catch (error) {
      console.error('Login failed:', error);
      toast.error('Login failed. Please try again.');
      return { success: false, error: error.response?.data?.message };
    } finally {
      setLoading(false);
    }
  };

  const logout = async () => {
    try {
      await authAPI.logout();
    } catch (error) {
      console.error('Logout error:', error);
    } finally {
      // Clear local state regardless of API call success
      setUser(null);
      setPermissions([]);
      localStorage.removeItem('access_token');
      localStorage.removeItem('refresh_token');
      toast.success('Logged out successfully');
    }
  };

  const refreshToken = async () => {
    try {
      const refreshToken = localStorage.getItem('refresh_token');
      if (!refreshToken) {
        throw new Error('No refresh token available');
      }

      const response = await authAPI.refresh(refreshToken);
      const { access_token } = response.data;

      localStorage.setItem('access_token', access_token);
      return access_token;

    } catch (error) {
      console.error('Token refresh failed:', error);
      // If refresh fails, logout user
      await logout();
      throw error;
    }
  };

  const hasPermission = (permission) => {
    if (!user) return false;

    // Admin has all permissions
    if (user.is_bot_admin) return true;

    // Check specific permissions
    return permissions.includes(permission);
  };

  const value = {
    user,
    loading,
    permissions,
    login,
    logout,
    refreshToken,
    hasPermission,
    checkAuthStatus,
  };

  return (
    <AuthContext.Provider value={value}>
      {children}
    </AuthContext.Provider>
  );
};