import React, { useState, useEffect } from 'react';
import {
  Box,
  Grid,
  Paper,
  Typography,
  Button,
  Card,
  CardContent,
  CardMedia,
  TextField,
  FormControl,
  InputLabel,
  Select,
  MenuItem,
  Chip,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  List,
  ListItem,
  ListItemText,
  ListItemSecondaryAction,
  IconButton,
  Alert,
  CircularProgress,
  Pagination,
} from '@mui/material';
import {
  Search,
  Movie,
  Tv,
  TrackChanges,
  Delete,
  PlayArrow,
  Star,
} from '@mui/icons-material';
import { mediaAPI } from '../services/api';
import { useAuth } from '../contexts/AuthContext';
import toast from 'react-hot-toast';

const MediaTools = () => {
  const { user } = useAuth();
  const [searchQuery, setSearchQuery] = useState('');
  const [searchType, setSearchType] = useState('movie');
  const [searchResults, setSearchResults] = useState([]);
  const [trackedShows, setTrackedShows] = useState([]);
  const [loading, setLoading] = useState(false);
  const [searching, setSearching] = useState(false);
  const [error, setError] = useState('');
  const [selectedItem, setSelectedItem] = useState(null);
  const [dialogOpen, setDialogOpen] = useState(false);
  const [currentPage, setCurrentPage] = useState(1);
  const [totalPages, setTotalPages] = useState(1);

  useEffect(() => {
    loadTrackedShows();
  }, []);

  const loadTrackedShows = async () => {
    try {
      setLoading(true);
      const response = await mediaAPI.getTrackedShows();
      setTrackedShows(response.data.tracked_shows || []);
    } catch (error) {
      console.error('Failed to load tracked shows:', error);
      setError('Failed to load tracked shows');
    } finally {
      setLoading(false);
    }
  };

  const handleSearch = async (page = 1) => {
    if (!searchQuery.trim()) {
      toast.error('Please enter a search query');
      return;
    }

    try {
      setSearching(true);
      setError('');

      let response;
      const limit = 10;

      switch (searchType) {
        case 'movie':
          response = await mediaAPI.searchMovies(searchQuery, limit);
          break;
        case 'tv':
          response = await mediaAPI.searchTV(searchQuery, limit);
          break;
        case 'anime':
          response = await mediaAPI.searchAnime(searchQuery, limit);
          break;
        default:
          return;
      }

      setSearchResults(response.data.results || []);
      setCurrentPage(page);
      setTotalPages(Math.ceil((response.data.total || 0) / limit));

    } catch (error) {
      console.error('Search failed:', error);
      setError('Search failed. Please try again.');
      setSearchResults([]);
    } finally {
      setSearching(false);
    }
  };

  const handleTrackShow = async (showData) => {
    try {
      const trackData = {
        show_id: showData.id.toString(),
        show_title: showData.title || showData.name,
        api_source: searchType === 'anime' ? 'anilist' : 'tmdb',
        show_type: searchType,
      };

      await mediaAPI.trackShow(trackData);
      toast.success(`Started tracking "${trackData.show_title}"`);
      loadTrackedShows();
    } catch (error) {
      console.error('Failed to track show:', error);
      toast.error('Failed to track show');
    }
  };

  const handleUntrackShow = async (trackId) => {
    try {
      await mediaAPI.untrackShow(trackId);
      toast.success('Show untracked successfully');
      loadTrackedShows();
    } catch (error) {
      console.error('Failed to untrack show:', error);
      toast.error('Failed to untrack show');
    }
  };

  const handleCreateWatchParty = async (mediaData) => {
    try {
      const watchPartyData = {
        title: `Watch Party: ${mediaData.title || mediaData.name}`,
        description: mediaData.overview || mediaData.description || '',
        scheduled_start_time: new Date(Date.now() + 24 * 60 * 60 * 1000).toISOString(), // Tomorrow
        media_poster_url: mediaData.poster_path
          ? `https://image.tmdb.org/t/p/w500${mediaData.poster_path}`
          : mediaData.coverImage?.large || '',
      };

      await mediaAPI.createWatchParty(watchPartyData);
      toast.success('Watch party created successfully!');
    } catch (error) {
      console.error('Failed to create watch party:', error);
      toast.error('Failed to create watch party');
    }
  };

  const openDetailsDialog = (item) => {
    setSelectedItem(item);
    setDialogOpen(true);
  };

  const renderSearchResults = () => {
    if (searching) {
      return (
        <Box sx={{ display: 'flex', justifyContent: 'center', p: 4 }}>
          <CircularProgress />
        </Box>
      );
    }

    if (searchResults.length === 0) {
      return (
        <Box sx={{ textAlign: 'center', p: 4 }}>
          <Typography variant="h6" color="text.secondary">
            No results found
          </Typography>
          <Typography variant="body2" color="text.secondary">
            Try adjusting your search query
          </Typography>
        </Box>
      );
    }

    return (
      <Grid container spacing={3}>
        {searchResults.map((item) => (
          <Grid item xs={12} sm={6} md={4} key={item.id}>
            <Card sx={{ height: '100%', cursor: 'pointer' }} onClick={() => openDetailsDialog(item)}>
              <CardMedia
                component="img"
                height="300"
                image={
                  item.poster_path
                    ? `https://image.tmdb.org/t/p/w500${item.poster_path}`
                    : item.coverImage?.large || '/placeholder-movie.jpg'
                }
                alt={item.title || item.name}
                sx={{ objectFit: 'cover' }}
              />
              <CardContent>
                <Typography variant="h6" gutterBottom noWrap>
                  {item.title || item.name}
                </Typography>

                <Box sx={{ display: 'flex', alignItems: 'center', mb: 1 }}>
                  {item.vote_average && (
                    <>
                      <Star sx={{ color: 'warning.main', mr: 0.5 }} />
                      <Typography variant="body2" sx={{ mr: 2 }}>
                        {item.vote_average.toFixed(1)}
                      </Typography>
                    </>
                  )}

                  <Chip
                    label={item.release_date ? new Date(item.release_date).getFullYear() :
                           item.first_air_date ? new Date(item.first_air_date).getFullYear() :
                           item.seasonYear || 'N/A'}
                    size="small"
                    variant="outlined"
                  />
                </Box>

                <Typography variant="body2" color="text.secondary" sx={{
                  display: '-webkit-box',
                  WebkitLineClamp: 3,
                  WebkitBoxOrient: 'vertical',
                  overflow: 'hidden',
                  textOverflow: 'ellipsis',
                }}>
                  {item.overview || item.description || 'No description available'}
                </Typography>

                <Box sx={{ display: 'flex', gap: 1, mt: 2 }}>
                  <Button
                    size="small"
                    variant="outlined"
                    startIcon={<TrackChanges />}
                    onClick={(e) => {
                      e.stopPropagation();
                      handleTrackShow(item);
                    }}
                  >
                    Track
                  </Button>

                  <Button
                    size="small"
                    variant="outlined"
                    startIcon={<PlayArrow />}
                    onClick={(e) => {
                      e.stopPropagation();
                      handleCreateWatchParty(item);
                    }}
                  >
                    Watch Party
                  </Button>
                </Box>
              </CardContent>
            </Card>
          </Grid>
        ))}
      </Grid>
    );
  };

  return (
    <Box sx={{ p: 3 }}>
      <Typography variant="h4" gutterBottom>
        Media Tools
      </Typography>

      <Typography variant="body1" color="text.secondary" sx={{ mb: 4 }}>
        Search for movies, TV shows, and anime. Track your favorites and create watch parties.
      </Typography>

      {error && (
        <Alert severity="error" sx={{ mb: 3 }}>
          {error}
        </Alert>
      )}

      {/* Search Section */}
      <Paper sx={{ p: 3, mb: 4 }}>
        <Typography variant="h6" gutterBottom>
          Search Media
        </Typography>

        <Grid container spacing={2} sx={{ mb: 3 }}>
          <Grid item xs={12} sm={6}>
            <TextField
              fullWidth
              label="Search Query"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              onKeyPress={(e) => e.key === 'Enter' && handleSearch()}
              placeholder="Enter movie, TV show, or anime title..."
            />
          </Grid>

          <Grid item xs={12} sm={3}>
            <FormControl fullWidth>
              <InputLabel>Media Type</InputLabel>
              <Select
                value={searchType}
                label="Media Type"
                onChange={(e) => setSearchType(e.target.value)}
              >
                <MenuItem value="movie">
                  <Box sx={{ display: 'flex', alignItems: 'center' }}>
                    <Movie sx={{ mr: 1 }} />
                    Movies
                  </Box>
                </MenuItem>
                <MenuItem value="tv">
                  <Box sx={{ display: 'flex', alignItems: 'center' }}>
                    <Tv sx={{ mr: 1 }} />
                    TV Shows
                  </Box>
                </MenuItem>
                <MenuItem value="anime">
                  <Box sx={{ display: 'flex', alignItems: 'center' }}>
                    <TrackChanges sx={{ mr: 1 }} />
                    Anime
                  </Box>
                </MenuItem>
              </Select>
            </FormControl>
          </Grid>

          <Grid item xs={12} sm={3}>
            <Button
              fullWidth
              variant="contained"
              startIcon={<Search />}
              onClick={() => handleSearch()}
              disabled={searching}
              sx={{ height: '56px' }}
            >
              {searching ? <CircularProgress size={24} /> : 'Search'}
            </Button>
          </Grid>
        </Grid>

        {/* Search Results */}
        {renderSearchResults()}

        {/* Pagination */}
        {searchResults.length > 0 && totalPages > 1 && (
          <Box sx={{ display: 'flex', justifyContent: 'center', mt: 3 }}>
            <Pagination
              count={totalPages}
              page={currentPage}
              onChange={(e, page) => handleSearch(page)}
              color="primary"
            />
          </Box>
        )}
      </Paper>

      {/* Tracked Shows */}
      <Paper sx={{ p: 3 }}>
        <Typography variant="h6" gutterBottom>
          Tracked Shows
        </Typography>

        {loading ? (
          <CircularProgress />
        ) : trackedShows.length === 0 ? (
          <Typography variant="body2" color="text.secondary">
            No tracked shows yet. Search for content above and click "Track" to add shows.
          </Typography>
        ) : (
          <List>
            {trackedShows.map((track) => (
              <ListItem key={track.id} divider>
                <ListItemText
                  primary={
                    <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                      <Typography variant="body1" sx={{ fontWeight: 'bold' }}>
                        {track.show_title}
                      </Typography>
                      <Chip
                        label={track.api_source.toUpperCase()}
                        size="small"
                        color="primary"
                        variant="outlined"
                      />
                      <Chip
                        label={track.show_type}
                        size="small"
                        color="secondary"
                        variant="outlined"
                      />
                    </Box>
                  }
                  secondary={
                    <Typography variant="body2" color="text.secondary">
                      Last checked: {new Date(track.last_checked).toLocaleDateString()}
                    </Typography>
                  }
                />
                <ListItemSecondaryAction>
                  <IconButton
                    edge="end"
                    color="error"
                    onClick={() => handleUntrackShow(track.id)}
                  >
                    <Delete />
                  </IconButton>
                </ListItemSecondaryAction>
              </ListItem>
            ))}
          </List>
        )}
      </Paper>

      {/* Details Dialog */}
      <Dialog open={dialogOpen} onClose={() => setDialogOpen(false)} maxWidth="md" fullWidth>
        <DialogTitle>
          {selectedItem?.title || selectedItem?.name}
        </DialogTitle>
        <DialogContent>
          {selectedItem && (
            <Grid container spacing={3}>
              <Grid item xs={12} sm={4}>
                <CardMedia
                  component="img"
                  height="300"
                  image={
                    selectedItem.poster_path
                      ? `https://image.tmdb.org/t/p/w500${selectedItem.poster_path}`
                      : selectedItem.coverImage?.large || '/placeholder-movie.jpg'
                  }
                  alt={selectedItem.title || selectedItem.name}
                  sx={{ borderRadius: 1 }}
                />
              </Grid>

              <Grid item xs={12} sm={8}>
                <Typography variant="h6" gutterBottom>
                  Overview
                </Typography>
                <Typography variant="body1" paragraph>
                  {selectedItem.overview || selectedItem.description || 'No description available'}
                </Typography>

                <Box sx={{ display: 'flex', gap: 2, flexWrap: 'wrap', mb: 2 }}>
                  {selectedItem.vote_average && (
                    <Chip
                      icon={<Star />}
                      label={`Rating: ${selectedItem.vote_average.toFixed(1)}`}
                      color="warning"
                      variant="outlined"
                    />
                  )}

                  {selectedItem.release_date && (
                    <Chip
                      label={`Released: ${new Date(selectedItem.release_date).getFullYear()}`}
                      variant="outlined"
                    />
                  )}

                  {selectedItem.genres && (
                    <Chip
                      label={`Genres: ${selectedItem.genres.map(g => g.name).join(', ')}`}
                      variant="outlined"
                    />
                  )}
                </Box>

                <Box sx={{ display: 'flex', gap: 1 }}>
                  <Button
                    variant="contained"
                    startIcon={<TrackChanges />}
                    onClick={() => {
                      handleTrackShow(selectedItem);
                      setDialogOpen(false);
                    }}
                  >
                    Track This Show
                  </Button>

                  <Button
                    variant="outlined"
                    startIcon={<PlayArrow />}
                    onClick={() => {
                      handleCreateWatchParty(selectedItem);
                      setDialogOpen(false);
                    }}
                  >
                    Create Watch Party
                  </Button>
                </Box>
              </Grid>
            </Grid>
          )}
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setDialogOpen(false)}>Close</Button>
        </DialogActions>
      </Dialog>
    </Box>
  );
};

export default MediaTools;