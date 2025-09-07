import React, { useState, useEffect } from 'react';
import {
  Box,
  Grid,
  Paper,
  Typography,
  Button,
  Card,
  CardContent,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  TextField,
  FormControl,
  InputLabel,
  Select,
  MenuItem,
  Chip,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  IconButton,
  Alert,
  CircularProgress,
} from '@mui/material';
import {
  Add,
  Edit,
  Delete,
  PlayArrow,
  Stop,
  People,
  AccessTime,
  EmojiEvents,
} from '@mui/icons-material';
import { DateTimePicker } from '@mui/x-date-pickers/DateTimePicker';
import { LocalizationProvider } from '@mui/x-date-pickers/LocalizationProvider';
import { AdapterDateFns } from '@mui/x-date-pickers/AdapterDateFns';
import { format } from 'date-fns';
import { giveawayAPI } from '../services/api';
import { useAuth } from '../contexts/AuthContext';
import toast from 'react-hot-toast';

const GiveawayManager = () => {
  const { user } = useAuth();
  const [giveaways, setGiveaways] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [dialogOpen, setDialogOpen] = useState(false);
  const [editingGiveaway, setEditingGiveaway] = useState(null);
  const [formData, setFormData] = useState({
    prize: '',
    winner_count: 1,
    channel_id: '',
    start_at: new Date(),
    end_at: new Date(Date.now() + 24 * 60 * 60 * 1000), // 24 hours from now
    description: '',
    required_role_id: '',
    max_entries_per_user: 1,
  });

  useEffect(() => {
    loadGiveaways();
  }, []);

  const loadGiveaways = async () => {
    try {
      setLoading(true);
      const response = await giveawayAPI.getGiveaways();
      setGiveaways(response.data.giveaways || []);
    } catch (error) {
      console.error('Failed to load giveaways:', error);
      setError('Failed to load giveaways');
    } finally {
      setLoading(false);
    }
  };

  const handleCreateGiveaway = () => {
    setEditingGiveaway(null);
    setFormData({
      prize: '',
      winner_count: 1,
      channel_id: '',
      start_at: new Date(),
      end_at: new Date(Date.now() + 24 * 60 * 60 * 1000),
      description: '',
      required_role_id: '',
      max_entries_per_user: 1,
    });
    setDialogOpen(true);
  };

  const handleEditGiveaway = (giveaway) => {
    setEditingGiveaway(giveaway);
    setFormData({
      prize: giveaway.prize,
      winner_count: giveaway.winner_count,
      channel_id: giveaway.channel_id,
      start_at: new Date(giveaway.start_at),
      end_at: new Date(giveaway.end_at),
      description: giveaway.description || '',
      required_role_id: giveaway.required_role_id || '',
      max_entries_per_user: giveaway.max_entries_per_user || 1,
    });
    setDialogOpen(true);
  };

  const handleDeleteGiveaway = async (giveawayId) => {
    if (!window.confirm('Are you sure you want to delete this giveaway?')) {
      return;
    }

    try {
      await giveawayAPI.deleteGiveaway(giveawayId);
      toast.success('Giveaway deleted successfully');
      loadGiveaways();
    } catch (error) {
      console.error('Failed to delete giveaway:', error);
      toast.error('Failed to delete giveaway');
    }
  };

  const handleEndGiveaway = async (giveawayId) => {
    if (!window.confirm('Are you sure you want to end this giveaway now?')) {
      return;
    }

    try {
      await giveawayAPI.endGiveaway(giveawayId);
      toast.success('Giveaway ended successfully');
      loadGiveaways();
    } catch (error) {
      console.error('Failed to end giveaway:', error);
      toast.error('Failed to end giveaway');
    }
  };

  const handleSubmit = async () => {
    // Validate form
    if (!formData.prize.trim()) {
      toast.error('Prize is required');
      return;
    }

    if (!formData.channel_id) {
      toast.error('Channel is required');
      return;
    }

    if (formData.end_at <= formData.start_at) {
      toast.error('End time must be after start time');
      return;
    }

    try {
      const giveawayData = {
        ...formData,
        start_at: formData.start_at.toISOString(),
        end_at: formData.end_at.toISOString(),
      };

      if (editingGiveaway) {
        await giveawayAPI.updateGiveaway(editingGiveaway.id, giveawayData);
        toast.success('Giveaway updated successfully');
      } else {
        await giveawayAPI.createGiveaway(giveawayData);
        toast.success('Giveaway created successfully');
      }

      setDialogOpen(false);
      loadGiveaways();
    } catch (error) {
      console.error('Failed to save giveaway:', error);
      toast.error('Failed to save giveaway');
    }
  };

  const getStatusColor = (status) => {
    switch (status) {
      case 'scheduled':
        return 'default';
      case 'active':
        return 'success';
      case 'ended':
        return 'warning';
      case 'cancelled':
        return 'error';
      default:
        return 'default';
    }
  };

  const getStatusText = (status) => {
    switch (status) {
      case 'scheduled':
        return 'Scheduled';
      case 'active':
        return 'Active';
      case 'ended':
        return 'Ended';
      case 'cancelled':
        return 'Cancelled';
      default:
        return status;
    }
  };

  const isGiveawayActive = (giveaway) => {
    const now = new Date();
    const start = new Date(giveaway.start_at);
    const end = new Date(giveaway.end_at);
    return now >= start && now <= end && giveaway.status === 'active';
  };

  if (loading) {
    return (
      <Box sx={{ p: 3 }}>
        <Typography variant="h4" gutterBottom>
          Giveaway Manager
        </Typography>
        <CircularProgress />
        <Typography sx={{ mt: 2 }}>Loading giveaways...</Typography>
      </Box>
    );
  }

  return (
    <LocalizationProvider dateAdapter={AdapterDateFns}>
      <Box sx={{ p: 3 }}>
        <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 3 }}>
          <Typography variant="h4" gutterBottom>
            Giveaway Manager
          </Typography>
          <Button
            variant="contained"
            startIcon={<Add />}
            onClick={handleCreateGiveaway}
          >
            Create Giveaway
          </Button>
        </Box>

        {error && (
          <Alert severity="error" sx={{ mb: 3 }}>
            {error}
          </Alert>
        )}

        {/* Stats Cards */}
        <Grid container spacing={3} sx={{ mb: 4 }}>
          <Grid item xs={12} sm={6} md={3}>
            <Card>
              <CardContent sx={{ textAlign: 'center' }}>
                <Typography variant="h4" color="primary" sx={{ fontWeight: 'bold' }}>
                  {giveaways.length}
                </Typography>
                <Typography variant="body2" color="text.secondary">
                  Total Giveaways
                </Typography>
              </CardContent>
            </Card>
          </Grid>

          <Grid item xs={12} sm={6} md={3}>
            <Card>
              <CardContent sx={{ textAlign: 'center' }}>
                <Typography variant="h4" color="success.main" sx={{ fontWeight: 'bold' }}>
                  {giveaways.filter(g => g.status === 'active').length}
                </Typography>
                <Typography variant="body2" color="text.secondary">
                  Active Giveaways
                </Typography>
              </CardContent>
            </Card>
          </Grid>

          <Grid item xs={12} sm={6} md={3}>
            <Card>
              <CardContent sx={{ textAlign: 'center' }}>
                <Typography variant="h4" color="warning.main" sx={{ fontWeight: 'bold' }}>
                  {giveaways.filter(g => g.status === 'ended').length}
                </Typography>
                <Typography variant="body2" color="text.secondary">
                  Completed Giveaways
                </Typography>
              </CardContent>
            </Card>
          </Grid>

          <Grid item xs={12} sm={6} md={3}>
            <Card>
              <CardContent sx={{ textAlign: 'center' }}>
                <Typography variant="h4" color="error.main" sx={{ fontWeight: 'bold' }}>
                  {giveaways.filter(g => g.status === 'scheduled').length}
                </Typography>
                <Typography variant="body2" color="text.secondary">
                  Scheduled Giveaways
                </Typography>
              </CardContent>
            </Card>
          </Grid>
        </Grid>

        {/* Giveaways Table */}
        <Paper sx={{ width: '100%', overflow: 'hidden' }}>
          <TableContainer>
            <Table>
              <TableHead>
                <TableRow>
                  <TableCell>Prize</TableCell>
                  <TableCell>Status</TableCell>
                  <TableCell>Winners</TableCell>
                  <TableCell>Start Time</TableCell>
                  <TableCell>End Time</TableCell>
                  <TableCell>Channel</TableCell>
                  <TableCell>Actions</TableCell>
                </TableRow>
              </TableHead>
              <TableBody>
                {giveaways.map((giveaway) => (
                  <TableRow key={giveaway.id}>
                    <TableCell>
                      <Box>
                        <Typography variant="body2" sx={{ fontWeight: 'bold' }}>
                          {giveaway.prize}
                        </Typography>
                        {giveaway.description && (
                          <Typography variant="caption" color="text.secondary">
                            {giveaway.description}
                          </Typography>
                        )}
                      </Box>
                    </TableCell>
                    <TableCell>
                      <Chip
                        label={getStatusText(giveaway.status)}
                        color={getStatusColor(giveaway.status)}
                        size="small"
                      />
                    </TableCell>
                    <TableCell>
                      <Box sx={{ display: 'flex', alignItems: 'center' }}>
                        <EmojiEvents sx={{ mr: 1, color: 'warning.main' }} />
                        {giveaway.winner_count}
                      </Box>
                    </TableCell>
                    <TableCell>
                      <Typography variant="body2">
                        {format(new Date(giveaway.start_at), 'MMM dd, HH:mm')}
                      </Typography>
                    </TableCell>
                    <TableCell>
                      <Typography variant="body2">
                        {format(new Date(giveaway.end_at), 'MMM dd, HH:mm')}
                      </Typography>
                    </TableCell>
                    <TableCell>
                      <Typography variant="body2">
                        #{giveaway.channel_name || `Channel ${giveaway.channel_id}`}
                      </Typography>
                    </TableCell>
                    <TableCell>
                      <Box sx={{ display: 'flex', gap: 1 }}>
                        <IconButton
                          size="small"
                          onClick={() => handleEditGiveaway(giveaway)}
                          disabled={giveaway.status === 'ended'}
                        >
                          <Edit />
                        </IconButton>

                        {isGiveawayActive(giveaway) && (
                          <IconButton
                            size="small"
                            color="error"
                            onClick={() => handleEndGiveaway(giveaway.id)}
                          >
                            <Stop />
                          </IconButton>
                        )}

                        <IconButton
                          size="small"
                          color="error"
                          onClick={() => handleDeleteGiveaway(giveaway.id)}
                          disabled={giveaway.status === 'active'}
                        >
                          <Delete />
                        </IconButton>
                      </Box>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </TableContainer>
        </Paper>

        {/* Create/Edit Dialog */}
        <Dialog open={dialogOpen} onClose={() => setDialogOpen(false)} maxWidth="md" fullWidth>
          <DialogTitle>
            {editingGiveaway ? 'Edit Giveaway' : 'Create New Giveaway'}
          </DialogTitle>
          <DialogContent>
            <Grid container spacing={3} sx={{ mt: 1 }}>
              <Grid item xs={12}>
                <TextField
                  fullWidth
                  label="Prize"
                  value={formData.prize}
                  onChange={(e) => setFormData(prev => ({ ...prev, prize: e.target.value }))}
                  required
                />
              </Grid>

              <Grid item xs={12}>
                <TextField
                  fullWidth
                  label="Description"
                  multiline
                  rows={3}
                  value={formData.description}
                  onChange={(e) => setFormData(prev => ({ ...prev, description: e.target.value }))}
                />
              </Grid>

              <Grid item xs={12} sm={6}>
                <FormControl fullWidth>
                  <InputLabel>Winner Count</InputLabel>
                  <Select
                    value={formData.winner_count}
                    label="Winner Count"
                    onChange={(e) => setFormData(prev => ({ ...prev, winner_count: e.target.value }))}
                  >
                    {[1, 2, 3, 4, 5].map(num => (
                      <MenuItem key={num} value={num}>{num}</MenuItem>
                    ))}
                  </Select>
                </FormControl>
              </Grid>

              <Grid item xs={12} sm={6}>
                <TextField
                  fullWidth
                  label="Max Entries Per User"
                  type="number"
                  value={formData.max_entries_per_user}
                  onChange={(e) => setFormData(prev => ({ ...prev, max_entries_per_user: parseInt(e.target.value) || 1 }))}
                  inputProps={{ min: 1 }}
                />
              </Grid>

              <Grid item xs={12} sm={6}>
                <DateTimePicker
                  label="Start Time"
                  value={formData.start_at}
                  onChange={(date) => setFormData(prev => ({ ...prev, start_at: date }))}
                  slotProps={{ textField: { fullWidth: true } }}
                />
              </Grid>

              <Grid item xs={12} sm={6}>
                <DateTimePicker
                  label="End Time"
                  value={formData.end_at}
                  onChange={(date) => setFormData(prev => ({ ...prev, end_at: date }))}
                  slotProps={{ textField: { fullWidth: true } }}
                />
              </Grid>

              <Grid item xs={12}>
                <TextField
                  fullWidth
                  label="Channel ID"
                  value={formData.channel_id}
                  onChange={(e) => setFormData(prev => ({ ...prev, channel_id: e.target.value }))}
                  required
                  helperText="Discord channel ID where the giveaway will be posted"
                />
              </Grid>

              <Grid item xs={12}>
                <TextField
                  fullWidth
                  label="Required Role ID (Optional)"
                  value={formData.required_role_id}
                  onChange={(e) => setFormData(prev => ({ ...prev, required_role_id: e.target.value }))}
                  helperText="Users must have this role to participate"
                />
              </Grid>
            </Grid>
          </DialogContent>
          <DialogActions>
            <Button onClick={() => setDialogOpen(false)}>Cancel</Button>
            <Button onClick={handleSubmit} variant="contained">
              {editingGiveaway ? 'Update' : 'Create'}
            </Button>
          </DialogActions>
        </Dialog>
      </Box>
    </LocalizationProvider>
  );
};

export default GiveawayManager;