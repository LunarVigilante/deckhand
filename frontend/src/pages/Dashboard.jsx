import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  Box,
  Grid,
  Paper,
  Typography,
  Card,
  CardContent,
  Button,
  Avatar,
  Chip,
  LinearProgress,
  Alert,
} from '@mui/material';
import {
  Edit,
  BarChart,
  CardGiftcard,
  Movie,
  Message,
  People,
  AccessTime,
  TrendingUp,
} from '@mui/icons-material';
import { useAuth } from '../contexts/AuthContext';
import { statsAPI } from '../services/api';

const Dashboard = () => {
  const navigate = useNavigate();
  const { user } = useAuth();
  const [stats, setStats] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  useEffect(() => {
    loadDashboardStats();
  }, []);

  const loadDashboardStats = async () => {
    try {
      setLoading(true);
      // Load basic stats - you might want to create a dedicated dashboard endpoint
      const [messageStats, voiceStats] = await Promise.all([
        statsAPI.getMessageStats({ limit: 1 }),
        statsAPI.getVoiceStats({ limit: 1 }),
      ]);

      setStats({
        messages: messageStats.data?.total || 0,
        voiceTime: voiceStats.data?.total_time || 0,
        activeUsers: 0, // Would need to be calculated from your stats
      });
    } catch (error) {
      console.error('Failed to load dashboard stats:', error);
      setError('Failed to load dashboard statistics');
    } finally {
      setLoading(false);
    }
  };

  const quickActions = [
    {
      title: 'Create Embed',
      description: 'Build rich Discord embeds with live preview',
      icon: <Edit sx={{ fontSize: 40, color: 'primary.main' }} />,
      path: '/embeds',
      color: '#5865f2',
    },
    {
      title: 'View Statistics',
      description: 'Analyze server activity and user engagement',
      icon: <BarChart sx={{ fontSize: 40, color: 'success.main' }} />,
      path: '/stats',
      color: '#57f287',
    },
    {
      title: 'Manage Giveaways',
      description: 'Create and monitor automated giveaways',
      icon: <CardGiftcard sx={{ fontSize: 40, color: 'warning.main' }} />,
      path: '/giveaways',
      color: '#fee75c',
    },
    {
      title: 'Media Tools',
      description: 'Search and track movies, TV shows, and anime',
      icon: <Movie sx={{ fontSize: 40, color: 'error.main' }} />,
      path: '/media',
      color: '#ed4245',
    },
  ];

  const recentActivity = [
    {
      type: 'embed',
      title: 'Embed posted',
      description: 'Welcome message template posted in #general',
      time: '2 hours ago',
      icon: <Edit sx={{ color: 'primary.main' }} />,
    },
    {
      type: 'giveaway',
      title: 'Giveaway ended',
      description: 'Discord Nitro giveaway completed with 156 participants',
      time: '5 hours ago',
      icon: <CardGiftcard sx={{ color: 'warning.main' }} />,
    },
    {
      type: 'media',
      title: 'Show tracked',
      description: 'Started tracking "Attack on Titan" for new episodes',
      time: '1 day ago',
      icon: <Movie sx={{ color: 'error.main' }} />,
    },
  ];

  return (
    <Box>
      <Typography variant="h4" gutterBottom sx={{ fontWeight: 'bold' }}>
        Dashboard
      </Typography>

      <Typography variant="body1" color="text.secondary" sx={{ mb: 4 }}>
        Welcome back, {user?.global_name || user?.username}! Here's an overview of your Discord bot.
      </Typography>

      {error && (
        <Alert severity="error" sx={{ mb: 3 }}>
          {error}
        </Alert>
      )}

      {/* User Profile Card */}
      <Paper sx={{ p: 3, mb: 4, background: 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)', color: 'white' }}>
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 3 }}>
          <Avatar
            src={user?.avatar_hash ? `https://cdn.discordapp.com/avatars/${user.user_id}/${user.avatar_hash}.png` : undefined}
            sx={{ width: 80, height: 80, border: '4px solid white' }}
          >
            {user?.username?.charAt(0).toUpperCase()}
          </Avatar>

          <Box sx={{ flexGrow: 1 }}>
            <Typography variant="h5" sx={{ fontWeight: 'bold', mb: 1 }}>
              {user?.global_name || user?.username}
            </Typography>
            <Typography variant="body1" sx={{ opacity: 0.9, mb: 2 }}>
              {user?.is_bot_admin ? 'Bot Administrator' : 'Bot User'}
            </Typography>
            <Box sx={{ display: 'flex', gap: 1 }}>
              <Chip
                label={`User ID: ${user?.user_id}`}
                sx={{ backgroundColor: 'rgba(255, 255, 255, 0.2)', color: 'white' }}
              />
              {user?.is_bot_admin && (
                <Chip
                  label="Admin"
                  sx={{ backgroundColor: 'rgba(255, 255, 255, 0.3)', color: 'white' }}
                />
              )}
            </Box>
          </Box>
        </Box>
      </Paper>

      {/* Stats Overview */}
      <Grid container spacing={3} sx={{ mb: 4 }}>
        <Grid item xs={12} sm={6} md={3}>
          <Card>
            <CardContent sx={{ textAlign: 'center' }}>
              <Message sx={{ fontSize: 48, color: 'primary.main', mb: 1 }} />
              <Typography variant="h4" sx={{ fontWeight: 'bold' }}>
                {loading ? '...' : (stats?.messages || 0).toLocaleString()}
              </Typography>
              <Typography variant="body2" color="text.secondary">
                Total Messages
              </Typography>
            </CardContent>
          </Card>
        </Grid>

        <Grid item xs={12} sm={6} md={3}>
          <Card>
            <CardContent sx={{ textAlign: 'center' }}>
              <AccessTime sx={{ fontSize: 48, color: 'success.main', mb: 1 }} />
              <Typography variant="h4" sx={{ fontWeight: 'bold' }}>
                {loading ? '...' : Math.floor((stats?.voiceTime || 0) / 3600)}h
              </Typography>
              <Typography variant="body2" color="text.secondary">
                Voice Time
              </Typography>
            </CardContent>
          </Card>
        </Grid>

        <Grid item xs={12} sm={6} md={3}>
          <Card>
            <CardContent sx={{ textAlign: 'center' }}>
              <People sx={{ fontSize: 48, color: 'warning.main', mb: 1 }} />
              <Typography variant="h4" sx={{ fontWeight: 'bold' }}>
                {loading ? '...' : (stats?.activeUsers || 0).toLocaleString()}
              </Typography>
              <Typography variant="body2" color="text.secondary">
                Active Users
              </Typography>
            </CardContent>
          </Card>
        </Grid>

        <Grid item xs={12} sm={6} md={3}>
          <Card>
            <CardContent sx={{ textAlign: 'center' }}>
              <TrendingUp sx={{ fontSize: 48, color: 'error.main', mb: 1 }} />
              <Typography variant="h4" sx={{ fontWeight: 'bold' }}>
                +12%
              </Typography>
              <Typography variant="body2" color="text.secondary">
                Growth Rate
              </Typography>
            </CardContent>
          </Card>
        </Grid>
      </Grid>

      {/* Quick Actions */}
      <Typography variant="h5" gutterBottom sx={{ fontWeight: 'bold', mb: 3 }}>
        Quick Actions
      </Typography>

      <Grid container spacing={3} sx={{ mb: 4 }}>
        {quickActions.map((action, index) => (
          <Grid item xs={12} sm={6} md={3} key={index}>
            <Card
              sx={{
                cursor: 'pointer',
                transition: 'transform 0.2s, box-shadow 0.2s',
                '&:hover': {
                  transform: 'translateY(-4px)',
                  boxShadow: 4,
                },
                height: '100%',
              }}
              onClick={() => navigate(action.path)}
            >
              <CardContent sx={{ textAlign: 'center', p: 3 }}>
                {action.icon}
                <Typography variant="h6" sx={{ mt: 2, mb: 1, fontWeight: 'bold' }}>
                  {action.title}
                </Typography>
                <Typography variant="body2" color="text.secondary">
                  {action.description}
                </Typography>
              </CardContent>
            </Card>
          </Grid>
        ))}
      </Grid>

      {/* Recent Activity */}
      <Grid container spacing={3}>
        <Grid item xs={12} md={8}>
          <Paper sx={{ p: 3 }}>
            <Typography variant="h5" gutterBottom sx={{ fontWeight: 'bold' }}>
              Recent Activity
            </Typography>

            {recentActivity.map((activity, index) => (
              <Box
                key={index}
                sx={{
                  display: 'flex',
                  alignItems: 'center',
                  py: 2,
                  borderBottom: index < recentActivity.length - 1 ? '1px solid #e0e0e0' : 'none',
                }}
              >
                <Box sx={{ mr: 2 }}>
                  {activity.icon}
                </Box>
                <Box sx={{ flexGrow: 1 }}>
                  <Typography variant="body1" sx={{ fontWeight: 'bold' }}>
                    {activity.title}
                  </Typography>
                  <Typography variant="body2" color="text.secondary">
                    {activity.description}
                  </Typography>
                </Box>
                <Typography variant="caption" color="text.secondary">
                  {activity.time}
                </Typography>
              </Box>
            ))}
          </Paper>
        </Grid>

        <Grid item xs={12} md={4}>
          <Paper sx={{ p: 3 }}>
            <Typography variant="h5" gutterBottom sx={{ fontWeight: 'bold' }}>
              System Status
            </Typography>

            <Box sx={{ mb: 2 }}>
              <Box sx={{ display: 'flex', justifyContent: 'space-between', mb: 1 }}>
                <Typography variant="body2">Bot Status</Typography>
                <Chip label="Online" color="success" size="small" />
              </Box>
              <LinearProgress variant="determinate" value={100} color="success" />
            </Box>

            <Box sx={{ mb: 2 }}>
              <Box sx={{ display: 'flex', justifyContent: 'space-between', mb: 1 }}>
                <Typography variant="body2">API Status</Typography>
                <Chip label="Healthy" color="success" size="small" />
              </Box>
              <LinearProgress variant="determinate" value={100} color="success" />
            </Box>

            <Box sx={{ mb: 2 }}>
              <Box sx={{ display: 'flex', justifyContent: 'space-between', mb: 1 }}>
                <Typography variant="body2">Database</Typography>
                <Chip label="Connected" color="success" size="small" />
              </Box>
              <LinearProgress variant="determinate" value={100} color="success" />
            </Box>

            <Typography variant="body2" color="text.secondary" sx={{ mt: 2 }}>
              Last updated: {new Date().toLocaleTimeString()}
            </Typography>
          </Paper>
        </Grid>
      </Grid>
    </Box>
  );
};

export default Dashboard;