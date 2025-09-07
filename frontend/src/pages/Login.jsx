import React, { useEffect, useState } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import {
  Box,
  Paper,
  Typography,
  Button,
  Alert,
  CircularProgress,
  Container,
  Grid,
  Card,
  CardContent,
} from '@mui/material';
import { Discord as DiscordIcon } from '@mui/icons-material';
import { useAuth } from '../contexts/AuthContext';

const Login = () => {
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const { login, loading } = useAuth();
  const [error, setError] = useState('');
  const [processing, setProcessing] = useState(false);

  useEffect(() => {
    // Check for authorization code in URL
    const code = searchParams.get('code');
    const error = searchParams.get('error');

    if (error) {
      setError(`Authentication failed: ${error}`);
      return;
    }

    if (code && !processing) {
      handleDiscordCallback(code);
    }
  }, [searchParams, processing]);

  const handleDiscordCallback = async (code) => {
    setProcessing(true);
    setError('');

    try {
      const result = await login(code);

      if (result.success) {
        navigate('/dashboard');
      } else {
        setError(result.error || 'Login failed');
      }
    } catch (err) {
      setError('An unexpected error occurred during login');
      console.error('Login error:', err);
    } finally {
      setProcessing(false);
    }
  };

  const handleDiscordLogin = () => {
    const clientId = import.meta.env.VITE_DISCORD_CLIENT_ID;
    const redirectUri = encodeURIComponent(import.meta.env.VITE_DISCORD_REDIRECT_URI || `${window.location.origin}/login`);
    const scope = 'identify guilds';

    const discordAuthUrl = `https://discord.com/api/oauth2/authorize?client_id=${clientId}&redirect_uri=${redirectUri}&response_type=code&scope=${scope}`;

    window.location.href = discordAuthUrl;
  };

  if (loading || processing) {
    return (
      <Box
        display="flex"
        justifyContent="center"
        alignItems="center"
        minHeight="100vh"
        sx={{ backgroundColor: 'background.default' }}
      >
        <Paper sx={{ p: 4, textAlign: 'center' }}>
          <CircularProgress size={60} sx={{ mb: 2 }} />
          <Typography variant="h6">
            {processing ? 'Completing login...' : 'Loading...'}
          </Typography>
        </Paper>
      </Box>
    );
  }

  return (
    <Box
      sx={{
        minHeight: '100vh',
        background: 'linear-gradient(135deg, #5865f2 0%, #7289da 100%)',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        p: 2,
      }}
    >
      <Container maxWidth="md">
        <Grid container spacing={4} alignItems="center">
          <Grid item xs={12} md={6}>
            <Box sx={{ textAlign: { xs: 'center', md: 'left' }, color: 'white' }}>
              <Typography variant="h2" component="h1" gutterBottom sx={{ fontWeight: 'bold' }}>
                Discord Bot
              </Typography>
              <Typography variant="h3" component="h2" gutterBottom sx={{ fontWeight: 'bold' }}>
                Control Panel
              </Typography>
              <Typography variant="h6" sx={{ mb: 4, opacity: 0.9 }}>
                Manage your Discord server with powerful tools for embeds, giveaways, statistics, and media management.
              </Typography>

              <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2, maxWidth: 300 }}>
                <Typography variant="body1" sx={{ fontWeight: 500 }}>
                  ✨ Create rich embeds with live preview
                </Typography>
                <Typography variant="body1" sx={{ fontWeight: 500 }}>
                  🎁 Run automated giveaways
                </Typography>
                <Typography variant="body1" sx={{ fontWeight: 500 }}>
                  📊 View detailed server statistics
                </Typography>
                <Typography variant="body1" sx={{ fontWeight: 500 }}>
                  🎬 Search and track media content
                </Typography>
              </Box>
            </Box>
          </Grid>

          <Grid item xs={12} md={6}>
            <Card sx={{
              backgroundColor: 'rgba(255, 255, 255, 0.95)',
              backdropFilter: 'blur(10px)',
              borderRadius: 3,
              boxShadow: '0 20px 40px rgba(0, 0, 0, 0.1)',
            }}>
              <CardContent sx={{ p: 4, textAlign: 'center' }}>
                <Typography variant="h4" component="h2" gutterBottom sx={{ color: '#5865f2', fontWeight: 'bold' }}>
                  Welcome Back
                </Typography>

                <Typography variant="body1" sx={{ mb: 4, color: 'text.secondary' }}>
                  Sign in with Discord to access your control panel
                </Typography>

                {error && (
                  <Alert severity="error" sx={{ mb: 3 }}>
                    {error}
                  </Alert>
                )}

                <Button
                  variant="contained"
                  size="large"
                  startIcon={<DiscordIcon />}
                  onClick={handleDiscordLogin}
                  sx={{
                    backgroundColor: '#5865f2',
                    '&:hover': {
                      backgroundColor: '#4752c4',
                    },
                    py: 1.5,
                    px: 4,
                    borderRadius: 3,
                    fontSize: '1.1rem',
                    fontWeight: 'bold',
                    textTransform: 'none',
                  }}
                  disabled={processing}
                >
                  {processing ? <CircularProgress size={24} /> : 'Login with Discord'}
                </Button>

                <Typography variant="body2" sx={{ mt: 3, color: 'text.secondary' }}>
                  By logging in, you agree to our terms of service and privacy policy.
                </Typography>
              </CardContent>
            </Card>
          </Grid>
        </Grid>
      </Container>
    </Box>
  );
};

export default Login;