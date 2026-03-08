"""initial schema

Revision ID: a84554b7ca53
Revises:
Create Date: 2026-02-22 19:03:14.817541

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'a84554b7ca53'
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('imported_urls',
    sa.Column('url', sa.String(), nullable=False),
    sa.Column('status', sa.String(), nullable=False),
    sa.Column('attempted_at', sa.String(), nullable=False),
    sa.Column('show_id', sa.String(), nullable=True),
    sa.Column('artist_count', sa.Integer(), nullable=False),
    sa.Column('track_count', sa.Integer(), nullable=False),
    sa.Column('error', sa.String(), nullable=True),
    sa.PrimaryKeyConstraint('url')
    )
    op.create_table('showlists',
    sa.Column('id', sa.String(), nullable=False),
    sa.Column('name', sa.String(), nullable=False),
    sa.Column('owner_user_id', sa.String(), nullable=False),
    sa.Column('created_at', sa.String(), nullable=False),
    sa.Column('spotify_playlist_id', sa.String(), nullable=True),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('show_tracks',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('show_id', sa.String(), nullable=False),
    sa.Column('track_uri', sa.String(), nullable=False),
    sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('show_tracks', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_show_tracks_show_id'), ['show_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_show_tracks_track_uri'), ['track_uri'], unique=False)

    op.create_table('shows',
    sa.Column('id', sa.String(), nullable=False),
    sa.Column('venue', sa.String(), nullable=False),
    sa.Column('date', sa.String(), nullable=False),
    sa.Column('created_at', sa.String(), nullable=False),
    sa.Column('ticket_url', sa.String(), nullable=True),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('user_loved_tracks',
    sa.Column('user_id', sa.String(), nullable=False),
    sa.Column('track_uri', sa.String(), nullable=False),
    sa.Column('track_name', sa.String(), nullable=False),
    sa.Column('artist_name', sa.String(), nullable=False),
    sa.Column('loved_at', sa.String(), nullable=False),
    sa.PrimaryKeyConstraint('user_id', 'track_uri')
    )
    op.create_table('showlist_shows',
    sa.Column('showlist_id', sa.String(), nullable=False),
    sa.Column('show_id', sa.String(), nullable=False),
    sa.Column('added_at', sa.String(), nullable=False),
    sa.Column('added_by_user_id', sa.String(), nullable=False),
    sa.ForeignKeyConstraint(['showlist_id'], ['showlists.id'], ),
    sa.ForeignKeyConstraint(['show_id'], ['shows.id'], ),
    sa.PrimaryKeyConstraint('showlist_id', 'show_id')
    )
    op.create_table('show_artists',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('show_id', sa.String(), nullable=False),
    sa.Column('artist_name', sa.String(), nullable=False),
    sa.Column('position', sa.Integer(), nullable=False),
    sa.Column('spotify_id', sa.String(), nullable=True),
    sa.ForeignKeyConstraint(['show_id'], ['shows.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('show_artists', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_show_artists_show_id'), ['show_id'], unique=False)


def downgrade():
    with op.batch_alter_table('show_artists', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_show_artists_show_id'))

    op.drop_table('show_artists')
    op.drop_table('showlist_shows')
    op.drop_table('user_loved_tracks')
    op.drop_table('shows')
    with op.batch_alter_table('show_tracks', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_show_tracks_track_uri'))
        batch_op.drop_index(batch_op.f('ix_show_tracks_show_id'))

    op.drop_table('show_tracks')
    op.drop_table('showlists')
    op.drop_table('imported_urls')
