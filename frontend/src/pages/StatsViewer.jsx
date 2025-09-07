import React, { useState, useEffect } from 'react';
import {
  Box,
  Grid,
  Paper,
  Typography,
  Card,
  CardContent,
  FormControl,
  InputLabel,
  Select,
  MenuItem,
  Chip,
  LinearProgress,
  Alert,
} from '@mui/material';
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
  LineChart,
  Line,
  PieChart,
  Pie,
  Cell,
} from 'recharts';
import { DatePicker } from '@mui/x-date-pickers/DatePicker';
import { LocalizationProvider } from '@mui/x-date-pickers/LocalizationProvider';
import { AdapterDateFns } from '@mui/x-date-pickers/AdapterDateFns';
import { format, subDays, startOfDay, endOfDay } from 'date-fns';
import { statsAPI } from '../services/api';
import { useAuth } from '../contexts/AuthContext';

const COLORS = ['#5865f2', '#57f287', '#fee75c', '#ed4245', '#eb459e', '#f783ac'];

const StatsViewer = () => {
  const { user } = useAuth();
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [timeRange, setTimeRange] = useState('7d');
  const [customStartDate, setCustomStartDate] = useState(subDays(new Date(), 7));
  const [customEndDate, setCustomEndDate] = useState(new Date());
  const [statsData, setStatsData] = useState({
    messageStats: [],
    voiceStats: [],
    inviteStats: [],
    topChannels: [],
    topUsers: [],
    activityTrends: [],
  });

  useEffect(() => {
    loadStats();
  }, [timeRange, customStartDate, customEndDate]);

  const loadStats = async () => {
    try {
      setLoading(true);
      setError('');

      const params = getTimeRangeParams();

      // Load different types of statistics
      const [messageResponse, voiceResponse, inviteResponse] = await Promise.all([
        statsAPI.getMessageStats(params),
        statsAPI.getVoiceStats(params),
        statsAPI.getInviteStats(params),
      ]);

      // Process and format the data
      const processedData = {
        messageStats: processMessageStats(messageResponse.data),
        voiceStats: processVoiceStats(voiceResponse.data),
        inviteStats: processInviteStats(inviteResponse.data),
        topChannels: calculateTopChannels(messageResponse.data),
        topUsers: calculateTopUsers(messageResponse.data),
        activityTrends: generateActivityTrends(messageResponse.data),
      };

      setStatsData(processedData);
    } catch (error) {
      console.error('Failed to load stats:', error);
      setError('Failed to load statistics data');
    } finally {
      setLoading(false);
    }
  };

  const getTimeRangeParams = () => {
    const now = new Date();
    let startDate, endDate;

    switch (timeRange) {
      case '1d':
        startDate = startOfDay(now);
        endDate = endOfDay(now);
        break;
      case '7d':
        startDate = subDays(now, 7);
        endDate = now;
        break;
      case '30d':
        startDate = subDays(now, 30);
        endDate = now;
        break;
      case '90d':
        startDate = subDays(now, 90);
        endDate = now;
        break;
      case 'custom':
        startDate = customStartDate;
        endDate = customEndDate;
        break;
      default:
        startDate = subDays(now, 7);
        endDate = now;
    }

    return {
      start_date: format(startDate, 'yyyy-MM-dd'),
      end_date: format(endDate, 'yyyy-MM-dd'),
    };
  };

  const processMessageStats = (data) => {
    // Process message statistics for charts
    return data.map(item => ({
      date: format(new Date(item.date), 'MMM dd'),
      messages: item.message_count,
      users: item.unique_users || 0,
    }));
  };

  const processVoiceStats = (data) => {
    // Process voice statistics
    return data.map(item => ({
      date: format(new Date(item.date), 'MMM dd'),
      voiceTime: Math.round(item.total_duration / 3600), // Convert to hours
      sessions: item.session_count || 0,
    }));
  };

  const processInviteStats = (data) => {
    // Process invite statistics
    return data.map(item => ({
      date: format(new Date(item.date), 'MMM dd'),
      invites: item.invite_count,
      uses: item.total_uses,
    }));
  };

  const calculateTopChannels = (data) => {
    // Calculate most active channels
    const channelStats = {};
    data.forEach(item => {
      if (item.channel_name) {
        if (!channelStats[item.channel_name]) {
          channelStats[item.channel_name] = 0;
        }
        channelStats[item.channel_name] += item.message_count;
      }
    });

    return Object.entries(channelStats)
      .map(([name, messages]) => ({ name, messages }))
      .sort((a, b) => b.messages - a.messages)
      .slice(0, 10);
  };

  const calculateTopUsers = (data) => {
    // Calculate most active users
    const userStats = {};
    data.forEach(item => {
      if (item.username) {
        if (!userStats[item.username]) {
          userStats[item.username] = 0;
        }
        userStats[item.username] += item.message_count;
      }
    });

    return Object.entries(userStats)
      .map(([name, messages]) => ({ name, messages }))
      .sort((a, b) => b.messages - a.messages)
      .slice(0, 10);
  };

  const generateActivityTrends = (data) => {
    // Generate activity trends data
    return data.map(item => ({
      date: format(new Date(item.date), 'MMM dd'),
      messages: item.message_count,
      voiceActivity: item.voice_time || 0,
      invites: item.invite_count || 0,
    }));
  };

  const formatNumber = (num) => {
    if (num >= 1000000) {
      return (num / 1000000).toFixed(1) + 'M';
    }
    if (num >= 1000) {
      return (num / 1000).toFixed(1) + 'K';
    }
    return num.toString();
  };

  const formatDuration = (seconds) => {
    const hours = Math.floor(seconds / 3600);
    const minutes = Math.floor((seconds % 3600) / 60);
    return `${hours}h ${minutes}m`;
  };

  if (loading) {
    return (
      <Box sx={{ p: 3 }}>
        <Typography variant="h4" gutterBottom>
          Statistics
        </Typography>
        <LinearProgress />
        <Typography sx={{ mt: 2 }}>Loading statistics...</Typography>
      </Box>
    );
  }

  return (
    <LocalizationProvider dateAdapter={AdapterDateFns}>
      <Box sx={{ p: 3 }}>
        <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 3 }}>
          <Typography variant="h4" gutterBottom>
            Server Statistics
          </Typography>

          <Box sx={{ display: 'flex', gap: 2, alignItems: 'center' }}>
            <FormControl size="small" sx={{ minWidth: 120 }}>
              <InputLabel>Time Range</InputLabel>
              <Select
                value={timeRange}
                label="Time Range"
                onChange={(e) => setTimeRange(e.target.value)}
              >
                <MenuItem value="1d">Last 24 Hours</MenuItem>
                <MenuItem value="7d">Last 7 Days</MenuItem>
                <MenuItem value="30d">Last 30 Days</MenuItem>
                <MenuItem value="90d">Last 90 Days</MenuItem>
                <MenuItem value="custom">Custom Range</MenuItem>
              </Select>
            </FormControl>

            {timeRange === 'custom' && (
              <>
                <DatePicker
                  label="Start Date"
                  value={customStartDate}
                  onChange={setCustomStartDate}
                  slotProps={{ textField: { size: 'small' } }}
                />
                <DatePicker
                  label="End Date"
                  value={customEndDate}
                  onChange={setCustomEndDate}
                  slotProps={{ textField: { size: 'small' } }}
                />
              </>
            )}
          </Box>
        </Box>

        {error && (
          <Alert severity="error" sx={{ mb: 3 }}>
            {error}
          </Alert>
        )}

        {/* Overview Cards */}
        <Grid container spacing={3} sx={{ mb: 4 }}>
          <Grid item xs={12} sm={6} md={3}>
            <Card>
              <CardContent sx={{ textAlign: 'center' }}>
                <Typography variant="h4" color="primary" sx={{ fontWeight: 'bold' }}>
                  {formatNumber(statsData.messageStats.reduce((sum, item) => sum + item.messages, 0))}
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
                <Typography variant="h4" color="success.main" sx={{ fontWeight: 'bold' }}>
                  {formatNumber(statsData.voiceStats.reduce((sum, item) => sum + item.voiceTime, 0))}h
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
                <Typography variant="h4" color="warning.main" sx={{ fontWeight: 'bold' }}>
                  {statsData.inviteStats.reduce((sum, item) => sum + item.uses, 0)}
                </Typography>
                <Typography variant="body2" color="text.secondary">
                  Invite Uses
                </Typography>
              </CardContent>
            </Card>
          </Grid>

          <Grid item xs={12} sm={6} md={3}>
            <Card>
              <CardContent sx={{ textAlign: 'center' }}>
                <Typography variant="h4" color="error.main" sx={{ fontWeight: 'bold' }}>
                  {statsData.topUsers.length}
                </Typography>
                <Typography variant="body2" color="text.secondary">
                  Active Users
                </Typography>
              </CardContent>
            </Card>
          </Grid>
        </Grid>

        {/* Charts */}
        <Grid container spacing={3}>
          {/* Message Activity Chart */}
          <Grid item xs={12} lg={8}>
            <Paper sx={{ p: 3 }}>
              <Typography variant="h6" gutterBottom>
                Message Activity
              </Typography>
              <ResponsiveContainer width="100%" height={300}>
                <BarChart data={statsData.messageStats}>
                  <CartesianGrid strokeDasharray="3 3" />
                  <XAxis dataKey="date" />
                  <YAxis />
                  <Tooltip />
                  <Legend />
                  <Bar dataKey="messages" fill="#5865f2" name="Messages" />
                  <Bar dataKey="users" fill="#57f287" name="Active Users" />
                </BarChart>
              </ResponsiveContainer>
            </Paper>
          </Grid>

          {/* Top Channels */}
          <Grid item xs={12} lg={4}>
            <Paper sx={{ p: 3 }}>
              <Typography variant="h6" gutterBottom>
                Most Active Channels
              </Typography>
              <Box sx={{ maxHeight: 300, overflow: 'auto' }}>
                {statsData.topChannels.map((channel, index) => (
                  <Box
                    key={channel.name}
                    sx={{
                      display: 'flex',
                      justifyContent: 'space-between',
                      alignItems: 'center',
                      py: 1,
                      borderBottom: index < statsData.topChannels.length - 1 ? '1px solid #e0e0e0' : 'none',
                    }}
                  >
                    <Typography variant="body2">
                      #{channel.name}
                    </Typography>
                    <Chip
                      label={formatNumber(channel.messages)}
                      size="small"
                      color="primary"
                      variant="outlined"
                    />
                  </Box>
                ))}
              </Box>
            </Paper>
          </Grid>

          {/* Voice Activity Chart */}
          <Grid item xs={12} lg={6}>
            <Paper sx={{ p: 3 }}>
              <Typography variant="h6" gutterBottom>
                Voice Activity
              </Typography>
              <ResponsiveContainer width="100%" height={300}>
                <LineChart data={statsData.voiceStats}>
                  <CartesianGrid strokeDasharray="3 3" />
                  <XAxis dataKey="date" />
                  <YAxis />
                  <Tooltip />
                  <Legend />
                  <Line
                    type="monotone"
                    dataKey="voiceTime"
                    stroke="#57f287"
                    strokeWidth={2}
                    name="Voice Hours"
                  />
                </LineChart>
              </ResponsiveContainer>
            </Paper>
          </Grid>

          {/* Top Users */}
          <Grid item xs={12} lg={6}>
            <Paper sx={{ p: 3 }}>
              <Typography variant="h6" gutterBottom>
                Most Active Users
              </Typography>
              <Box sx={{ maxHeight: 300, overflow: 'auto' }}>
                {statsData.topUsers.map((user, index) => (
                  <Box
                    key={user.name}
                    sx={{
                      display: 'flex',
                      justifyContent: 'space-between',
                      alignItems: 'center',
                      py: 1,
                      borderBottom: index < statsData.topUsers.length - 1 ? '1px solid #e0e0e0' : 'none',
                    }}
                  >
                    <Typography variant="body2">
                      {user.name}
                    </Typography>
                    <Chip
                      label={formatNumber(user.messages)}
                      size="small"
                      color="secondary"
                      variant="outlined"
                    />
                  </Box>
                ))}
              </Box>
            </Paper>
          </Grid>

          {/* Activity Trends */}
          <Grid item xs={12}>
            <Paper sx={{ p: 3 }}>
              <Typography variant="h6" gutterBottom>
                Activity Trends
              </Typography>
              <ResponsiveContainer width="100%" height={300}>
                <LineChart data={statsData.activityTrends}>
                  <CartesianGrid strokeDasharray="3 3" />
                  <XAxis dataKey="date" />
                  <YAxis />
                  <Tooltip />
                  <Legend />
                  <Line
                    type="monotone"
                    dataKey="messages"
                    stroke="#5865f2"
                    strokeWidth={2}
                    name="Messages"
                  />
                  <Line
                    type="monotone"
                    dataKey="voiceActivity"
                    stroke="#57f287"
                    strokeWidth={2}
                    name="Voice Activity"
                  />
                  <Line
                    type="monotone"
                    dataKey="invites"
                    stroke="#fee75c"
                    strokeWidth={2}
                    name="Invites"
                  />
                </LineChart>
              </ResponsiveContainer>
            </Paper>
          </Grid>
        </Grid>
      </Box>
    </LocalizationProvider>
  );
};

export default StatsViewer;