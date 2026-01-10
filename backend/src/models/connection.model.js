const mongoose = require('mongoose')

const ConnectionSchema = new mongoose.Schema(
  {
    requester: { type: mongoose.Schema.Types.ObjectId, ref: 'User', required: true },
    recipient: { type: mongoose.Schema.Types.ObjectId, ref: 'User', required: true },
    status: { type: String, enum: ['pending', 'accepted', 'rejected'], default: 'pending' },
    message: { type: String }, // optional message with request
    respondedAt: { type: Date },
    connectedAt: { type: Date }, // when connection was accepted
  },
  { timestamps: true }
)

// Prevent duplicate requests
ConnectionSchema.index({ requester: 1, recipient: 1 }, { unique: true })

module.exports = mongoose.models.Connection || mongoose.model('Connection', ConnectionSchema)
