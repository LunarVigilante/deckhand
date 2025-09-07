import React, { useState, useEffect, useRef } from 'react';
import { Box, Paper, Grid, TextField, Button, Typography, Alert, CircularProgress, Card, CardContent } from '@mui/material';
import { Save, Preview, Clear, PlayArrow } from '@mui/icons-material';
import EditorJS from '@editorjs/editorjs';
import Header from '@editorjs/header';
import List from '@editorjs/list';
import Quote from '@editorjs/quote';
import Delimiter from '@editorjs/delimiter';
import Embed from '@editorjs/embed';
import Image from '@editorjs/image';
import Link from '@editorjs/link';
import api from '../services/api';

const EmbedBuilder = () => {
  const [templateName, setTemplateName] = useState('');
  const [description, setDescription] = useState('');
  const [embedData, setEmbedData] = useState({
    title: '',
    description: '',
    color: '#5865f2',
    fields: [],
    footer: { text: '' },
    author: { name: '' },
    thumbnail: { url: '' },
    image: { url: '' }
  });
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');
  const [templates, setTemplates] = useState([]);
  const [selectedTemplate, setSelectedTemplate] = useState(null);
  const [showPreview, setShowPreview] = useState(false);

  const editorRef = useRef(null);
  const editorInstance = useRef(null);

  useEffect(() => {
    loadTemplates();
    initializeEditor();

    return () => {
      if (editorInstance.current) {
        editorInstance.current.destroy();
      }
    };
  }, []);

  const initializeEditor = () => {
    if (editorRef.current && !editorInstance.current) {
      editorInstance.current = new EditorJS({
        holder: editorRef.current,
        tools: {
          header: {
            class: Header,
            inlineToolbar: true,
            config: {
              placeholder: 'Enter a header',
              levels: [2, 3, 4],
              defaultLevel: 2
            }
          },
          list: {
            class: List,
            inlineToolbar: true
          },
          quote: Quote,
          delimiter: Delimiter,
          embed: {
            class: Embed,
            config: {
              services: {
                youtube: true,
                vimeo: true,
                twitter: true,
                instagram: true
              }
            }
          },
          image: {
            class: Image,
            config: {
              endpoints: {
                byFile: '/api/upload/image'
              }
            }
          },
          link: Link
        },
        data: {},
        onChange: handleEditorChange,
        placeholder: "Start creating your embed content..."
      });
    }
  };

  const handleEditorChange = async () => {
    if (editorInstance.current) {
      try {
        const outputData = await editorInstance.current.save();
        // Convert Editor.js data to Discord embed format
        const discordEmbed = convertEditorToEmbed(outputData);
        setEmbedData(prev => ({
          ...prev,
          description: discordEmbed.description
        }));
      } catch (error) {
        console.error('Saving failed:', error);
      }
    }
  };

  const convertEditorToEmbed = (editorData) => {
    let description = '';

    editorData.blocks.forEach(block => {
      switch (block.type) {
        case 'header':
          const level = block.data.level;
          const headerText = block.data.text;
          const prefix = '#'.repeat(level - 1);
          description += `${prefix} ${headerText}\n\n`;
          break;
        case 'paragraph':
          description += `${block.data.text}\n\n`;
          break;
        case 'list':
          block.data.items.forEach(item => {
            const marker = block.data.style === 'ordered' ? '1.' : '•';
            description += `${marker} ${item}\n`;
          });
          description += '\n';
          break;
        case 'quote':
          description += `> ${block.data.text}\n`;
          if (block.data.caption) {
            description += `> — ${block.data.caption}\n`;
          }
          description += '\n';
          break;
        case 'delimiter':
          description += '---\n\n';
          break;
        default:
          break;
      }
    });

    return { description: description.trim() };
  };

  const loadTemplates = async () => {
    try {
      setLoading(true);
      const response = await api.get('/embeds/templates');
      setTemplates(response.data.templates || []);
    } catch (error) {
      setError('Failed to load templates');
      console.error('Load templates error:', error);
    } finally {
      setLoading(false);
    }
  };

  const loadTemplate = async (templateId) => {
    try {
      setLoading(true);
      const response = await api.get(`/embeds/templates/${templateId}`);
      const template = response.data;

      setSelectedTemplate(template);
      setTemplateName(template.template_name);
      setDescription(template.description || '');
      setEmbedData(template.embed_json);

      // Load content into Editor.js
      if (editorInstance.current && template.embed_json.description) {
        // Convert Discord embed back to Editor.js format
        const editorData = convertEmbedToEditor(template.embed_json);
        await editorInstance.current.render(editorData);
      }

      setError('');
    } catch (error) {
      setError('Failed to load template');
      console.error('Load template error:', error);
    } finally {
      setLoading(false);
    }
  };

  const convertEmbedToEditor = (embedData) => {
    // Convert Discord embed description to Editor.js blocks
    const blocks = [];

    if (embedData.description) {
      const paragraphs = embedData.description.split('\n\n');
      paragraphs.forEach(paragraph => {
        if (paragraph.trim()) {
          blocks.push({
            type: 'paragraph',
            data: { text: paragraph.trim() }
          });
        }
      });
    }

    return { blocks };
  };

  const validateTemplate = async () => {
    if (!templateName.trim()) {
      setError('Template name is required');
      return false;
    }

    try {
      const response = await api.post(`/embeds/templates/${templateName}/validate`, {
        embed_json: embedData
      });

      if (!response.data.name_available) {
        setError('Template name already exists');
        return false;
      }

      if (!response.data.embed_valid) {
        setError('Invalid embed data');
        return false;
      }

      return true;
    } catch (error) {
      setError('Validation failed');
      return false;
    }
  };

  const saveTemplate = async () => {
    if (!(await validateTemplate())) {
      return;
    }

    try {
      setSaving(true);
      setError('');
      setSuccess('');

      const templateData = {
        template_name: templateName.trim(),
        embed_json: embedData,
        description: description.trim() || null
      };

      let response;
      if (selectedTemplate) {
        response = await api.put(`/embeds/templates/${selectedTemplate.id}`, templateData);
        setSuccess('Template updated successfully!');
      } else {
        response = await api.post('/embeds/templates', templateData);
        setSuccess('Template created successfully!');
      }

      await loadTemplates();
      setSelectedTemplate(response.data);

    } catch (error) {
      const errorMessage = error.response?.data?.message || 'Failed to save template';
      setError(errorMessage);
      console.error('Save template error:', error);
    } finally {
      setSaving(false);
    }
  };

  const createNewTemplate = () => {
    setSelectedTemplate(null);
    setTemplateName('');
    setDescription('');
    setEmbedData({
      title: '',
      description: '',
      color: '#5865f2',
      fields: [],
      footer: { text: '' },
      author: { name: '' },
      thumbnail: { url: '' },
      image: { url: '' }
    });

    if (editorInstance.current) {
      editorInstance.current.clear();
    }

    setError('');
    setSuccess('');
  };

  const generatePreview = () => {
    setShowPreview(true);
  };

  const renderEmbedPreview = () => {
    const embed = embedData;

    return (
      <Card sx={{
        maxWidth: 520,
        bgcolor: '#36393f',
        color: '#dcddde',
        borderRadius: 1
      }}>
        <CardContent sx={{ p: 2 }}>
          {/* Author */}
          {embed.author?.name && (
            <Box sx={{ display: 'flex', alignItems: 'center', mb: 1 }}>
              {embed.author.icon_url && (
                <Box
                  component="img"
                  src={embed.author.icon_url}
                  sx={{ width: 20, height: 20, borderRadius: '50%', mr: 1 }}
                />
              )}
              <Typography variant="body2" sx={{ fontWeight: 'bold', mr: 1 }}>
                {embed.author.name}
              </Typography>
              {embed.author.url && (
                <Typography variant="body2" sx={{ color: '#00aff4' }}>
                  {embed.author.url}
                </Typography>
              )}
            </Box>
          )}

          {/* Title */}
          {embed.title && (
            <Typography variant="h6" sx={{ mb: 1, fontWeight: 'bold' }}>
              {embed.title}
            </Typography>
          )}

          {/* Description */}
          {embed.description && (
            <Typography variant="body2" sx={{ mb: 2, whiteSpace: 'pre-wrap' }}>
              {embed.description}
            </Typography>
          )}

          {/* Fields */}
          {embed.fields?.map((field, index) => (
            <Box key={index} sx={{
              display: 'inline-block',
              minWidth: field.inline ? '200px' : '100%',
              mr: field.inline ? 2 : 0,
              mb: 1,
              verticalAlign: 'top'
            }}>
              <Typography variant="body2" sx={{ fontWeight: 'bold' }}>
                {field.name}
              </Typography>
              <Typography variant="body2">
                {field.value}
              </Typography>
            </Box>
          ))}

          {/* Image */}
          {embed.image?.url && (
            <Box
              component="img"
              src={embed.image.url}
              sx={{
                maxWidth: '100%',
                maxHeight: 300,
                borderRadius: 1,
                mt: 2
              }}
            />
          )}

          {/* Thumbnail */}
          {embed.thumbnail?.url && !embed.image?.url && (
            <Box
              component="img"
              src={embed.thumbnail.url}
              sx={{
                width: 80,
                height: 80,
                borderRadius: 1,
                float: 'right',
                ml: 2
              }}
            />
          )}

          {/* Footer */}
          {embed.footer?.text && (
            <Box sx={{ display: 'flex', alignItems: 'center', mt: 2, pt: 1, borderTop: '1px solid #4f545c' }}>
              {embed.footer.icon_url && (
                <Box
                  component="img"
                  src={embed.footer.icon_url}
                  sx={{ width: 20, height: 20, mr: 1 }}
                />
              )}
              <Typography variant="caption" sx={{ color: '#72767d' }}>
                {embed.footer.text}
              </Typography>
            </Box>
          )}
        </CardContent>
      </Card>
    );
  };

  return (
    <Box sx={{ p: 3 }}>
      <Typography variant="h4" gutterBottom>
        Embed Builder
      </Typography>

      {error && (
        <Alert severity="error" sx={{ mb: 2 }}>
          {error}
        </Alert>
      )}

      {success && (
        <Alert severity="success" sx={{ mb: 2 }}>
          {success}
        </Alert>
      )}

      <Grid container spacing={3}>
        {/* Template Settings */}
        <Grid item xs={12} md={4}>
          <Paper sx={{ p: 2 }}>
            <Typography variant="h6" gutterBottom>
              Template Settings
            </Typography>

            <TextField
              fullWidth
              label="Template Name"
              value={templateName}
              onChange={(e) => setTemplateName(e.target.value)}
              sx={{ mb: 2 }}
            />

            <TextField
              fullWidth
              label="Description"
              multiline
              rows={3}
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              sx={{ mb: 2 }}
            />

            <Box sx={{ display: 'flex', gap: 1, flexWrap: 'wrap' }}>
              <Button
                variant="contained"
                startIcon={saving ? <CircularProgress size={20} /> : <Save />}
                onClick={saveTemplate}
                disabled={saving}
              >
                {selectedTemplate ? 'Update' : 'Save'}
              </Button>

              <Button
                variant="outlined"
                startIcon={<Clear />}
                onClick={createNewTemplate}
              >
                New
              </Button>

              <Button
                variant="outlined"
                startIcon={<Preview />}
                onClick={generatePreview}
              >
                Preview
              </Button>
            </Box>
          </Paper>

          {/* Template List */}
          <Paper sx={{ p: 2, mt: 2 }}>
            <Typography variant="h6" gutterBottom>
              Your Templates
            </Typography>

            {loading ? (
              <CircularProgress />
            ) : (
              <Box sx={{ maxHeight: 300, overflow: 'auto' }}>
                {templates.map((template) => (
                  <Box
                    key={template.id}
                    sx={{
                      p: 1,
                      mb: 1,
                      border: '1px solid #ddd',
                      borderRadius: 1,
                      cursor: 'pointer',
                      '&:hover': { bgcolor: '#f5f5f5' }
                    }}
                    onClick={() => loadTemplate(template.id)}
                  >
                    <Typography variant="body2" sx={{ fontWeight: 'bold' }}>
                      {template.template_name}
                    </Typography>
                    <Typography variant="caption" color="text.secondary">
                      {new Date(template.updated_at).toLocaleDateString()}
                    </Typography>
                  </Box>
                ))}
              </Box>
            )}
          </Paper>
        </Grid>

        {/* Editor */}
        <Grid item xs={12} md={8}>
          <Paper sx={{ p: 2 }}>
            <Typography variant="h6" gutterBottom>
              Content Editor
            </Typography>

            <Box
              ref={editorRef}
              sx={{
                minHeight: 400,
                border: '1px solid #ddd',
                borderRadius: 1,
                p: 2,
                '& .ce-block__content': {
                  maxWidth: 'none'
                },
                '& .ce-toolbar__content': {
                  maxWidth: 'none'
                }
              }}
            />

            {/* Embed Settings */}
            <Box sx={{ mt: 3 }}>
              <Typography variant="h6" gutterBottom>
                Embed Settings
              </Typography>

              <Grid container spacing={2}>
                <Grid item xs={12} sm={6}>
                  <TextField
                    fullWidth
                    label="Title"
                    value={embedData.title}
                    onChange={(e) => setEmbedData(prev => ({ ...prev, title: e.target.value }))}
                  />
                </Grid>

                <Grid item xs={12} sm={6}>
                  <TextField
                    fullWidth
                    label="Color"
                    type="color"
                    value={embedData.color}
                    onChange={(e) => setEmbedData(prev => ({ ...prev, color: e.target.value }))}
                  />
                </Grid>

                <Grid item xs={12} sm={6}>
                  <TextField
                    fullWidth
                    label="Author Name"
                    value={embedData.author?.name || ''}
                    onChange={(e) => setEmbedData(prev => ({
                      ...prev,
                      author: { ...prev.author, name: e.target.value }
                    }))}
                  />
                </Grid>

                <Grid item xs={12} sm={6}>
                  <TextField
                    fullWidth
                    label="Footer Text"
                    value={embedData.footer?.text || ''}
                    onChange={(e) => setEmbedData(prev => ({
                      ...prev,
                      footer: { ...prev.footer, text: e.target.value }
                    }))}
                  />
                </Grid>

                <Grid item xs={12} sm={6}>
                  <TextField
                    fullWidth
                    label="Thumbnail URL"
                    value={embedData.thumbnail?.url || ''}
                    onChange={(e) => setEmbedData(prev => ({
                      ...prev,
                      thumbnail: { ...prev.thumbnail, url: e.target.value }
                    }))}
                  />
                </Grid>

                <Grid item xs={12} sm={6}>
                  <TextField
                    fullWidth
                    label="Image URL"
                    value={embedData.image?.url || ''}
                    onChange={(e) => setEmbedData(prev => ({
                      ...prev,
                      image: { ...prev.image, url: e.target.value }
                    }))}
                  />
                </Grid>
              </Grid>
            </Box>
          </Paper>

          {/* Preview */}
          {showPreview && (
            <Paper sx={{ p: 2, mt: 2 }}>
              <Typography variant="h6" gutterBottom>
                Preview
              </Typography>
              {renderEmbedPreview()}
            </Paper>
          )}
        </Grid>
      </Grid>
    </Box>
  );
};

export default EmbedBuilder;