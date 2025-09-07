import React from 'react';
import { BrowserRouter as Router, Routes, Route, Navigate } from 'react-router-dom';
import { ThemeProvider, createTheme } from '@mui/material/styles';
import { CssBaseline, Box } from '@mui/material';
import { Toaster } from 'react-hot-toast';

// Components
import Navbar from './components/Navbar';
import Login from './pages/Login';
import Dashboard from './pages/Dashboard';
import EmbedBuilder from './components/EmbedBuilder';
import StatsViewer from './pages/StatsViewer';
import GiveawayManager from './pages/GiveawayManager';
import MediaTools from './pages/MediaTools';
import Profile from './pages/Profile';

// Context
import { AuthProvider, useAuth } from './contexts/AuthContext';

// Theme
const theme = createTheme({
  palette: {
    mode: 'dark',
    primary: {
      main: '#5865f2', // Discord blue
    },
    secondary: {
      main: '#57f287', // Discord green
    },
    background: {
      default: '#36393f', // Discord dark
      paper: '#2f3136',   // Discord darker
    },
    text: {
      primary: '#dcddde', // Discord light gray
      secondary: '#b9bbbe', // Discord gray
    },
  },
  typography: {
    fontFamily: '"Roboto", "Helvetica", "Arial", sans-serif',
    h4: {
      fontWeight: 600,
    },
    h5: {
      fontWeight: 600,
    },
    h6: {
      fontWeight: 600,
    },
  },
  components: {
    MuiButton: {
      styleOverrides: {
        root: {
          textTransform: 'none',
          borderRadius: 8,
        },
      },
    },
    MuiPaper: {
      styleOverrides: {
        root: {
          borderRadius: 8,
          backgroundImage: 'none',
        },
      },
    },
    MuiCard: {
      styleOverrides: {
        root: {
          borderRadius: 8,
          backgroundImage: 'none',
        },
      },
    },
  },
});

// Protected Route Component
const ProtectedRoute = ({ children }) => {
  const { user, loading } = useAuth();

  if (loading) {
    return (
      <Box
        display="flex"
        justifyContent="center"
        alignItems="center"
        minHeight="100vh"
      >
        <div>Loading...</div>
      </Box>
    );
  }

  return user ? children : <Navigate to="/login" />;
};

// App Router Component
const AppRouter = () => {
  const { user } = useAuth();

  return (
    <Box sx={{ display: 'flex', minHeight: '100vh' }}>
      {user && <Navbar />}
      <Box
        component="main"
        sx={{
          flexGrow: 1,
          p: user ? 3 : 0,
          backgroundColor: 'background.default',
          minHeight: '100vh',
        }}
      >
        <Routes>
          <Route
            path="/login"
            element={user ? <Navigate to="/dashboard" /> : <Login />}
          />
          <Route
            path="/dashboard"
            element={
              <ProtectedRoute>
                <Dashboard />
              </ProtectedRoute>
            }
          />
          <Route
            path="/embeds"
            element={
              <ProtectedRoute>
                <EmbedBuilder />
              </ProtectedRoute>
            }
          />
          <Route
            path="/stats"
            element={
              <ProtectedRoute>
                <StatsViewer />
              </ProtectedRoute>
            }
          />
          <Route
            path="/giveaways"
            element={
              <ProtectedRoute>
                <GiveawayManager />
              </ProtectedRoute>
            }
          />
          <Route
            path="/media"
            element={
              <ProtectedRoute>
                <MediaTools />
              </ProtectedRoute>
            }
          />
          <Route
            path="/profile"
            element={
              <ProtectedRoute>
                <Profile />
              </ProtectedRoute>
            }
          />
          <Route
            path="/"
            element={<Navigate to={user ? "/dashboard" : "/login"} />}
          />
          <Route
            path="*"
            element={<Navigate to={user ? "/dashboard" : "/login"} />}
          />
        </Routes>
      </Box>
    </Box>
  );
};

// Main App Component
function App() {
  return (
    <ThemeProvider theme={theme}>
      <CssBaseline />
      <AuthProvider>
        <Router>
          <AppRouter />
        </Router>
      </AuthProvider>
      <Toaster
        position="top-right"
        toastOptions={{
          duration: 4000,
          style: {
            background: '#36393f',
            color: '#dcddde',
            border: '1px solid #5865f2',
          },
        }}
      />
    </ThemeProvider>
  );
}

export default App;