import React, { useState, useEffect } from 'react';
import {
  Box,
  Paper,
  Typography,
  Avatar,
  Grid,
  TextField,
  Button,
  Alert,
  Card,
  CardContent,
  Chip,
  Divider,
  List,
  ListItem,
  ListItemText,
  ListItemIcon,
  CircularProgress,
} from '@mui/material';
import {
  Person,
  Email,
  Security,
  AccessTime,
  AdminPanelSettings,
  Save,
  Cancel,
} from '@mui/icons-material';
import { useAuth } from '../contexts/AuthContext';
import { userAPI } from '../services/api';
import toast from 'react-hot-toast';

const Profile = () => {
  const { user, logout } = useAuth();
  const [profile, setProfile] = useState(null);
  const [permissions, setPermissions] = useState([]);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');
  const [editMode, setEditMode] = useState(false);
  const [formData, setFormData] = useState({
    username: '',
    global_name: '',
  });

  useEffect(() => {
    loadProfile();
  }, []);

  const loadProfile = async () => {
    try {
      setLoading(true);
      const [profileResponse, permissionsResponse] = await Promise.all([
        userAPI.getProfile(),
        userAPI.getPermissions(),
      ]);

      setProfile(profileResponse.data);
      setPermissions(permissionsResponse.data.permissions || []);
      setFormData({
        username: profileResponse.data.username || '',
        global_name: profileResponse.data.global_name || '',
      });
    } catch (error) {
      console.error('Failed to load profile:', error);
      setError('Failed to load profile data');
    } finally {
      setLoading(false);
    }
  };

  const handleSave = async () => {
    try {
      setSaving(true);
      setError('');

      await userAPI.updateProfile(formData);
      toast.success('Profile updated successfully');
      setEditMode(false);
      loadProfile();
    } catch (error) {
      console.error('Failed to update profile:', error);
      setError('Failed to update profile');
    } finally {
      setSaving(false);
    }
  };

  const handleCancel = () => {
    setFormData({
      username: profile?.username || '',
      global_name: profile?.global_name || '',
    });
    setEditMode(false);
    setError('');
  };

  if (loading) {
    return (
      <Box sx={{ p: 3 }}>
        <Typography variant="h4" gutterBottom>
          Profile
        </Typography>
        <CircularProgress />
        <Typography sx={{ mt: 2 }}>Loading profile...</Typography>
      </Box>
    );
  }

  return (
    <Box sx={{ p: 3 }}>
      <Typography variant="h4" gutterBottom>
        Profile Settings
      </Typography>

      <Typography variant="body1" color="text.secondary" sx={{ mb: 4 }}>
        Manage your account settings and view your permissions.
      </Typography>

      {error && (
        <Alert severity="error" sx={{ mb: 3 }}>
          {error}
        </Alert>
      )}

      <Grid container spacing={4}>
        {/* Profile Information */}
        <Grid item xs={12} lg={8}>
          <Paper sx={{ p: 3 }}>
            <Box sx={{ display: 'flex', alignItems: 'center', mb: 3 }}>
              <Avatar
                src={profile?.avatar_hash ? `https://cdn.discordapp.com/avatars/${profile.user_id}/${profile.avatar_hash}.png` : undefined}
                sx={{ width: 80, height: 80, mr: 3 }}
              >
                {profile?.username?.charAt(0).toUpperCase()}
              </Avatar>

              <Box sx={{ flexGrow: 1 }}>
                <Typography variant="h5" sx={{ fontWeight: 'bold' }}>
                  {profile?.global_name || profile?.username}
                </Typography>
                <Typography variant="body2" color="text.secondary">
                  User ID: {profile?.user_id}
                </Typography>
                <Typography variant="body2" color="text.secondary">
                  Last Login: {profile?.last_login ? new Date(profile.last_login).toLocaleString() : 'Never'}
                </Typography>
              </Box>

              <Box sx={{ display: 'flex', gap: 1 }}>
                {!editMode ? (
                  <Button
                    variant="outlined"
                    onClick={() => setEditMode(true)}
                  >
                    Edit Profile
                  </Button>
                ) : (
                  <>
                    <Button
                      variant="contained"
                      startIcon={saving ? <CircularProgress size={20} /> : <Save />}
                      onClick={handleSave}
                      disabled={saving}
                    >
                      Save
                    </Button>
                    <Button
                      variant="outlined"
                      startIcon={<Cancel />}
                      onClick={handleCancel}
                      disabled={saving}
                    >
                      Cancel
                    </Button>
                  </>
                )}
              </Box>
            </Box>

            <Divider sx={{ mb: 3 }} />

            <Grid container spacing={3}>
              <Grid item xs={12} sm={6}>
                <TextField
                  fullWidth
                  label="Username"
                  value={editMode ? formData.username : profile?.username || ''}
                  onChange={(e) => setFormData(prev => ({ ...prev, username: e.target.value }))}
                  disabled={!editMode}
                  InputProps={{
                    startAdornment: <Person sx={{ mr: 1, color: 'action.active' }} />,
                  }}
                />
              </Grid>

              <Grid item xs={12} sm={6}>
                <TextField
                  fullWidth
                  label="Display Name"
                  value={editMode ? formData.global_name : profile?.global_name || ''}
                  onChange={(e) => setFormData(prev => ({ ...prev, global_name: e.target.value }))}
                  disabled={!editMode}
                  InputProps={{
                    startAdornment: <Person sx={{ mr: 1, color: 'action.active' }} />,
                  }}
                />
              </Grid>

              <Grid item xs={12}>
                <TextField
                  fullWidth
                  label="User ID"
                  value={profile?.user_id || ''}
                  disabled
                  InputProps={{
                    startAdornment: <Security sx={{ mr: 1, color: 'action.active' }} />,
                  }}
                />
              </Grid>

              <Grid item xs={12} sm={6}>
                <TextField
                  fullWidth
                  label="Account Created"
                  value={profile?.created_at ? new Date(profile.created_at).toLocaleDateString() : ''}
                  disabled
                  InputProps={{
                    startAdornment: <AccessTime sx={{ mr: 1, color: 'action.active' }} />,
                  }}
                />
              </Grid>

              <Grid item xs={12} sm={6}>
                <TextField
                  fullWidth
                  label="Last Login"
                  value={profile?.last_login ? new Date(profile.last_login).toLocaleString() : 'Never'}
                  disabled
                  InputProps={{
                    startAdornment: <AccessTime sx={{ mr: 1, color: 'action.active' }} />,
                  }}
                />
              </Grid>
            </Grid>
          </Paper>
        </Grid>

        {/* Permissions and Status */}
        <Grid item xs={12} lg={4}>
          <Paper sx={{ p: 3, mb: 3 }}>
            <Typography variant="h6" gutterBottom sx={{ display: 'flex', alignItems: 'center' }}>
              <AdminPanelSettings sx={{ mr: 1 }} />
              Account Status
            </Typography>

            <Box sx={{ mb: 2 }}>
              <Chip
                label={profile?.is_bot_admin ? 'Bot Administrator' : 'Regular User'}
                color={profile?.is_bot_admin ? 'error' : 'default'}
                variant={profile?.is_bot_admin ? 'filled' : 'outlined'}
                sx={{ mb: 1 }}
              />
            </Box>

            <Typography variant="body2" color="text.secondary">
              {profile?.is_bot_admin
                ? 'You have full administrative access to all bot features and settings.'
                : 'You have access to standard bot features based on your Discord server roles.'
              }
            </Typography>
          </Paper>

          <Paper sx={{ p: 3 }}>
            <Typography variant="h6" gutterBottom>
              Permissions
            </Typography>

            {permissions.length === 0 ? (
              <Typography variant="body2" color="text.secondary">
                No specific permissions assigned.
              </Typography>
            ) : (
              <List dense>
                {permissions.map((permission, index) => (
                  <ListItem key={index}>
                    <ListItemIcon sx={{ minWidth: 36 }}>
                      <Security sx={{ color: 'success.main' }} />
                    </ListItemIcon>
                    <ListItemText
                      primary={
                        <Typography variant="body2" sx={{ textTransform: 'capitalize' }}>
                          {permission.replace('_', ' ').replace('.', ' → ')}
                        </Typography>
                      }
                    />
                  </ListItem>
                ))}
              </List>
            )}

            <Divider sx={{ my: 2 }} />

            <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
              Permissions are automatically determined based on your roles in the Discord server.
            </Typography>

            <Button
              fullWidth
              variant="outlined"
              color="error"
              onClick={logout}
            >
              Logout
            </Button>
          </Paper>
        </Grid>
      </Grid>

      {/* Recent Activity */}
      <Paper sx={{ p: 3, mt: 4 }}>
        <Typography variant="h6" gutterBottom>
          Recent Activity
        </Typography>

        <Typography variant="body2" color="text.secondary">
          Activity tracking will be displayed here in future updates.
        </Typography>

        {/* Placeholder for future activity feed */}
        <Box sx={{ mt: 2, p: 2, bgcolor: 'action.hover', borderRadius: 1 }}>
          <Typography variant="body2" color="text.secondary">
            • Embed template "Welcome Message" created - 2 hours ago
          </Typography>
          <Typography variant="body2" color="text.secondary">
            • Giveaway "Discord Nitro" ended with 156 participants - 5 hours ago
          </Typography>
          <Typography variant="body2" color="text.secondary">
            • Started tracking "Attack on Titan" for new episodes - 1 day ago
          </Typography>
        </Box>
      </Paper>
    </Box>
  );
};

export default Profile;